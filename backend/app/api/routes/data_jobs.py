import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core.config import settings
from app.data_jobs import (
    TEMPLATE_VERSION,
    cleanup_expired_data_jobs,
    create_template_workbook_bytes,
    data_job_public,
    ensure_job_storage_dir,
    new_upload_path,
    process_job,
    recover_interrupted_data_jobs,
    validate_xlsx_archive,
)
from app.models import (
    DataJob,
    DataJobPublic,
    DataJobsPublic,
    DataJobStatus,
    DataJobType,
)
from app.utils import resolve_pagination

router = APIRouter(prefix="/system/data-jobs", tags=["data-jobs"])


def _ensure_job_capacity(session: SessionDep) -> None:
    # Serialize capacity checks across workers until the new job is committed.
    session.exec(select(func.pg_advisory_xact_lock(484_671_032))).one()
    active_count = session.exec(
        select(func.count())
        .select_from(DataJob)
        .where(
            col(DataJob.status).in_([DataJobStatus.PENDING, DataJobStatus.PROCESSING])
        )
    ).one()
    if active_count >= settings.DATA_JOB_MAX_ACTIVE_JOBS:
        raise HTTPException(
            status_code=429,
            detail="Too many data jobs are already running",
        )


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=DataJobsPublic,
)
def read_data_jobs(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    cleanup_expired_data_jobs()
    recover_interrupted_data_jobs()
    offset, max_results = resolve_pagination(
        page=page, page_size=page_size, skip=skip, limit=limit
    )
    count = session.exec(select(func.count()).select_from(DataJob)).one()
    jobs = session.exec(
        select(DataJob)
        .order_by(col(DataJob.created_at).desc())
        .offset(offset)
        .limit(max_results)
    ).all()
    return DataJobsPublic(data=[data_job_public(job) for job in jobs], count=count)


@router.post(
    "/export",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=DataJobPublic,
)
def create_export_job(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> Any:
    _ensure_job_capacity(session)
    job = DataJob(job_type=DataJobType.EXPORT, created_by=current_user.id)
    session.add(job)
    session.commit()
    session.refresh(job)
    background_tasks.add_task(process_job, job.id)
    return data_job_public(job)


@router.post(
    "/import",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=DataJobPublic,
)
async def create_import_job(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> Any:
    _ensure_job_capacity(session)
    suffix = Path(file.filename or "import.xlsx").suffix.lower()
    if suffix != ".xlsx":
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")
    file_path = new_upload_path(suffix=suffix)
    uploaded_bytes = 0
    try:
        with file_path.open("xb") as destination:
            while chunk := await file.read(1024 * 1024):
                uploaded_bytes += len(chunk)
                if uploaded_bytes > settings.DATA_JOB_MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Uploaded file exceeds the allowed size",
                    )
                destination.write(chunk)
        if uploaded_bytes == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        try:
            validate_xlsx_archive(file_path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        file_path.unlink(missing_ok=True)
        raise
    job = DataJob(
        job_type=DataJobType.IMPORT,
        created_by=current_user.id,
        source_file_path=str(file_path),
    )
    try:
        session.add(job)
        session.commit()
        session.refresh(job)
    except Exception:
        session.rollback()
        file_path.unlink(missing_ok=True)
        raise
    background_tasks.add_task(process_job, job.id)
    return data_job_public(job)


@router.get(
    "/template",
    dependencies=[Depends(get_current_active_superuser)],
)
def download_template() -> FileResponse:
    storage_dir = ensure_job_storage_dir()
    template_path = storage_dir / f"homefin-import-template-{TEMPLATE_VERSION}.xlsx"
    if not template_path.exists():
        template_path.write_bytes(create_template_workbook_bytes())
    return FileResponse(
        template_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=template_path.name,
    )


@router.get(
    "/{job_id}/result",
    dependencies=[Depends(get_current_active_superuser)],
)
def download_result_file(session: SessionDep, job_id: uuid.UUID) -> FileResponse:
    job = session.get(DataJob, job_id)
    if not job or not job.result_file_path:
        raise HTTPException(status_code=404, detail="Result file not found")
    file_path = Path(job.result_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Result file expired")
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=file_path.name,
    )


@router.get(
    "/{job_id}/errors",
    dependencies=[Depends(get_current_active_superuser)],
)
def download_error_file(session: SessionDep, job_id: uuid.UUID) -> FileResponse:
    job = session.get(DataJob, job_id)
    if not job or not job.error_file_path:
        raise HTTPException(status_code=404, detail="Error file not found")
    file_path = Path(job.error_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Error file expired")
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=file_path.name,
    )
