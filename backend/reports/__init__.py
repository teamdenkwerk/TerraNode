"""
backend/reports/__init__.py
"""
from backend.reports.router import router as reports_router
from backend.reports.summary_service import compute_report_summary
from backend.reports.pdf_generator import generate_audit_pdf

__all__ = ["reports_router", "compute_report_summary", "generate_audit_pdf"]
