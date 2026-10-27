"""
Promueve un usuario existente a administrador.

Uso:  python scripts/crear_admin.py <username>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session, select  # noqa: E402

from db.database import engine  # noqa: E402
from models import User  # noqa: E402
from models.enums import UserRole  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Uso: python scripts/crear_admin.py <username>")
    username = sys.argv[1].strip().lower()
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if user is None:
            sys.exit(f"No existe el usuario '{username}'. Regístralo primero en /api/v1/auth/register")
        user.role = UserRole.admin
        session.add(user)
        session.commit()
        print(f"'{username}' ahora es administrador. Vuelve a iniciar sesión para obtener el nuevo token.")


if __name__ == "__main__":
    main()
