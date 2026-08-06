"""Simple Jinja2-based template engine with preview and placeholder validation.

Features:
- TemplateEngine: register templates (id, body, subject), render with context, preview
- extract_placeholders: returns set of expected placeholders from template
- TemplateStore: in-memory store for templates (can be replaced with DB-backed store later)

This keeps persistence optional so migrations are not required immediately. Production
hardening (DB model, Alembic migration, sanitization, template versioning, storage,
access control) should be added in follow-up tasks.
"""
from __future__ import annotations

from typing import Dict, Any, Optional, Set
import logging
from jinja2 import Environment, meta, TemplateSyntaxError

logger = logging.getLogger(__name__)

JINJA_ENV = Environment()


class TemplateError(Exception):
    pass


def extract_placeholders(template_src: str) -> Set[str]:
    """Return a set of top-level placeholder names used in the template source."""
    try:
        ast = JINJA_ENV.parse(template_src)
    except TemplateSyntaxError as e:
        logger.exception("Template syntax error during placeholder extraction")
        raise TemplateError(str(e))
    return meta.find_undeclared_variables(ast)


from sqlalchemy.orm import Session
from app.models.notification_models import NotificationTemplate


class TemplateEngine:
    def __init__(self, store: Optional[object] = None):
        # If no explicit store provided, default to in-memory store for tests and
        # simple use. Production callers should pass a DB-backed session to the
        # per-method calls below.
        self.store = store or TemplateStore()

    def register_template(self, template_id: str, subject: str, body: str, db: Optional[Session] = None) -> None:
        # Validate syntax
        try:
            JINJA_ENV.parse(body)
            JINJA_ENV.parse(subject)
        except TemplateSyntaxError as e:
            raise TemplateError(f"Syntax error in template: {e}")

        if db is not None:
            # Persist to DB (upsert by name+language+channel is out-of-scope here;
            # keep simple: create a new template row with provided name and default language/version)
            tpl = NotificationTemplate(
                name=template_id,
                subject=subject,
                body=body,
                placeholders_json=list(extract_placeholders(subject) | extract_placeholders(body)),
                channel="UNKNOWN",
                created_by=None,
            )
            db.add(tpl)
            db.flush()
            return

        # Default behaviour: in-memory store (keeps existing tests working)
        self.store.save(template_id, {"subject": subject, "body": body})

    def get_template(self, template_id: str, db: Optional[Session] = None) -> Optional[Dict[str, str]]:
        if db is not None:
            # Return the latest active template with this name
            tpl = (
                db.query(NotificationTemplate)
                .filter(NotificationTemplate.name == template_id, NotificationTemplate.is_active.is_(True))
                .order_by(NotificationTemplate.version.desc())
                .first()
            )
            if tpl is None:
                return None
            return {"subject": tpl.subject or "", "body": tpl.body or ""}

        return self.store.get(template_id)

    def preview(self, template_id: str, context: Dict[str, Any], db: Optional[Session] = None) -> Dict[str, str]:
        t = self.get_template(template_id, db=db)
        if not t:
            raise TemplateError("template_not_found")
        subject_tpl = JINJA_ENV.from_string(t["subject"])
        body_tpl = JINJA_ENV.from_string(t["body"])
        try:
            rendered_subject = subject_tpl.render(**context)
            rendered_body = body_tpl.render(**context)
        except Exception as e:
            logger.exception("Template render failed")
            raise TemplateError(str(e))
        # Fallback: if subject still contains Python-style single-brace placeholders like {name}, try format()
        if '{' in rendered_subject and '}' in rendered_subject:
            try:
                rendered_subject = rendered_subject.format(**context)
            except Exception:
                # ignore format errors, keep rendered_subject as-is
                pass
        return {"subject": rendered_subject, "body": rendered_body}

    def validate_context(self, template_id: str, context: Dict[str, Any], db: Optional[Session] = None) -> Dict[str, Any]:
        t = self.get_template(template_id, db=db)
        if not t:
            raise TemplateError("template_not_found")
        expected = extract_placeholders(t["subject"]) | extract_placeholders(t["body"])
        missing = [k for k in expected if k not in context]
        return {"missing": missing, "expected": sorted(expected)}


class TemplateStore:
    """In-memory template store kept for backward compatibility with tests.

    Production callers should pass a DB session into the TemplateEngine methods
    to persist templates in the NotificationTemplate model instead.
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, str]] = {}

    def save(self, template_id: str, payload: Dict[str, str]) -> None:
        self._store[template_id] = payload

    def get(self, template_id: str) -> Optional[Dict[str, str]]:
        return self._store.get(template_id)

    def list_ids(self):
        return list(self._store.keys())


# Provide a module-level engine instance for ease of use in other modules
engine = TemplateEngine()
