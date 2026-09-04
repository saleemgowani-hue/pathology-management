from werkzeug.security import generate_password_hash, check_password_hash

from db.models import Tenant, User

ROLES = ["admin", "receptionist", "technician", "doctor", "accountant"]
STAFF_ROLES = ["receptionist", "technician", "doctor", "accountant"]


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def find_tenant_by_code(session, lab_code: str):
    return session.query(Tenant).filter_by(lab_code=lab_code.strip().upper()).first()


def authenticate(session, lab_code: str, username: str, password: str):
    """Returns (user, tenant, error_message)."""
    tenant = find_tenant_by_code(session, lab_code)
    if not tenant:
        return None, None, "Lab Code not found. Double-check it or register a new lab."
    user = session.query(User).filter_by(tenant_id=tenant.id, username=username.strip()).first()
    if not user or not verify_password(password, user.password_hash):
        return None, None, "Invalid username or password."
    if not user.active:
        return None, None, "Your account is awaiting administrator approval. Please check back later."
    return user, tenant, None


def create_admin_user(session, tenant_id: int, full_name: str, username: str, password: str, mobile: str = ""):
    """The one and only admin for a brand-new tenant — created at
    registration time, active immediately (nobody else exists yet to
    approve them)."""
    user = User(
        tenant_id=tenant_id, username=username.strip(), full_name=full_name.strip(),
        role="admin", mobile=mobile.strip(), active=True,
        password_hash=hash_password(password),
    )
    session.add(user)
    session.commit()
    return user


def join_existing_lab(session, tenant_id: int, full_name: str, username: str, password: str, role: str, mobile: str = ""):
    """A staff member joining a lab that already exists. Always
    pending approval — there is no bootstrap case here since the
    tenant's admin already exists by definition."""
    if role not in STAFF_ROLES:
        return None, "Please choose a valid role."
    if session.query(User).filter_by(tenant_id=tenant_id, username=username.strip()).first():
        return None, "That username is already taken at this lab. Please choose another."
    user = User(
        tenant_id=tenant_id, username=username.strip(), full_name=full_name.strip(),
        role=role, mobile=mobile.strip(), active=False,
        password_hash=hash_password(password),
    )
    session.add(user)
    session.commit()
    return user, None
