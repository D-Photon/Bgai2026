import logging
from datetime import datetime

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fpdf import FPDF
from sqlalchemy import text
from sqlmodel import Session, select

from database import create_db_and_tables, engine
from models import DEPARTMENT_SUBJECTS, Student, StudentCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BGAI Student Exam Registration", version="1.1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


class DuplicateRegistrationError(Exception):
    pass


def render_form(request: Request, values=None, error=None, status_code=200):
    return templates.TemplateResponse(
        "regform.html",
        {
            "request": request,
            "departments": list(DEPARTMENT_SUBJECTS),
            "subjects_by_department": DEPARTMENT_SUBJECTS,
            "error": error,
            "values": values or {},
        },
        status_code=status_code,
    )


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def registration_form(request: Request):
    return render_form(request)


@app.post("/register")
def register_student(
    request: Request,
    first_name: str = Form(...),
    middle_name: str = Form(""),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    student_class: str = Form(...),
    department: str = Form(...),
    subjects: list[str] = Form(...),
):
    values = {
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "student_class": student_class,
        "department": department,
        "subjects": subjects,
    }
    try:
        payload = StudentCreate(
            first_name=first_name,
            middle_name=middle_name or None,
            last_name=last_name,
            email=email,
            phone=phone,
            student_class=student_class,
            department=department,
            subjects=subjects,
        )
        name_parts = [payload.first_name, payload.middle_name, payload.last_name]
        full_name_key = " ".join(" ".join(part for part in name_parts if part).lower().split())

        with Session(engine) as session:
            # Serialize registrations for the same normalized name to prevent concurrent duplicates.
            with session.begin():
                session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:name_key))"),
                    {"name_key": full_name_key},
                )
                existing = session.exec(
                    select(Student.id).where(Student.full_name_key == full_name_key)
                ).first()
                if existing is not None:
                    raise DuplicateRegistrationError

                exam_year = datetime.now().year
                session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                    {"lock_key": f"exam-number:{exam_year}"},
                )
                exam_prefix = f"BGAI/GMCC/{exam_year}/"
                existing_numbers = session.exec(
                    select(Student.exam_number).where(Student.exam_number.like(f"{exam_prefix}%"))
                ).all()
                used_numbers = [
                    int(number[len(exam_prefix):])
                    for number in existing_numbers
                    if number[len(exam_prefix):].isdigit()
                ]
                exam_number = f"{exam_prefix}{max(used_numbers, default=0) + 1:03d}"

                student = Student(
                    **payload.model_dump(),
                    full_name_key=full_name_key,
                    exam_number=exam_number,
                )
                session.add(student)
                session.flush()
            session.refresh(student)

        # Post/Redirect/Get: reloading the confirmation performs only a GET, not another insert.
        return RedirectResponse(
            url=f"/registration/{student.download_token}",
            status_code=303,
        )
    except DuplicateRegistrationError:
        error = "A registration already exists for this full name. Please check the name or contact the administrator."
    except ValueError as exc:
        error = str(exc)
    except Exception:
        logger.exception("Student registration failed")
        error = "We could not save your registration. Please check your details and try again."
    return render_form(request, values=values, error=error, status_code=400)


@app.get("/registration/{download_token}", response_class=HTMLResponse)
def registration_confirmation(request: Request, download_token: str):
    with Session(engine) as session:
        student = session.exec(
            select(Student).where(Student.download_token == download_token)
        ).first()
    if student is None:
        raise HTTPException(status_code=404, detail="Registration not found")
    return templates.TemplateResponse(
        "success.html", {"request": request, "student": student}
    )


@app.get("/students/{download_token}/registration.pdf")
def download_registration(download_token: str):
    with Session(engine) as session:
        student = session.exec(
            select(Student).where(Student.download_token == download_token)
        ).first()
    if student is None:
        raise HTTPException(status_code=404, detail="Registration not found")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_text_color(24, 74, 56)
    pdf.set_font("Helvetica", "B", 17)
    pdf.cell(0, 12, "BEST GRADE AID INITIATIVE", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(85, 99, 91)
    pdf.cell(0, 8, "Student Preparatory Examination Registration", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    pdf.set_draw_color(220, 229, 223)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(7)
    pdf.set_text_color(35, 45, 40)
    details = [
        ("Exam number", student.exam_number),
        ("Student name", " ".join(x for x in [student.first_name, student.middle_name, student.last_name] if x)),
        ("Email", student.email),
        ("Phone", student.phone),
        ("Class", student.student_class),
        ("Department", student.department),
        ("Registration date", student.created_at.strftime("%d %B %Y")),
    ]
    for label, value in details:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(42, 9, f"{label}:")
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 9, str(value), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 9, "Registered subjects", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    for subject in student.subjects:
        pdf.cell(0, 8, f"- {subject}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(9)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(85, 99, 91)
    pdf.multi_cell(0, 6, "Please keep this form for your records. English and Mathematics are compulsory subjects.")
    output = bytes(pdf.output())
    safe_name = f"{student.exam_number.replace('/', '-')}-registration.pdf"
    return Response(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )



