# Backend · MyWishList

API REST en FastAPI + SQLAlchemy para MyWishList.

## Desarrollo

La aplicación **se niega a arrancar sin `SECRET_KEY`**: usar la clave pública
de desarrollo permitiría forjar tokens JWT de cualquier usuario. Para levantar
el entorno local:

```bash
cd backend
cp .env.example .env
# Edita .env y define una SECRET_KEY propia, por ejemplo:
#   SECRET_KEY=$(openssl rand -hex 32)
# Swagger UI (/docs) se oculta al usar una clave real; si la quieres en
# desarrollo, añade ENABLE_DOCS=1 al .env.
uv sync
uv run uvicorn backend.main:app --reload
```

## Pruebas

```bash
cd backend
uv run pytest
```

## Recuperar una cuenta (contraseña temporal)

La aplicación no recoge correo electrónico ni verifica usuarios, así que la
recuperación de contraseña la realiza quien administra la instancia:

```bash
# Genera una contraseña temporal aleatoria (14 caracteres alfanuméricos)
uv run reset-password alex

# O define una contraseña concreta
uv run reset-password alex --password "nueva-clave-123"
```

El comando normaliza el nombre de usuario (igual que el registro y el login),
actualiza su hash Argon2 e incrementa la versión de credenciales, por lo que
**todas las sesiones abiertas dejan de ser válidas inmediatamente**. Imprime la
contraseña temporal en la terminal: comunícala por un canal de confianza y pide
al usuario que la cambie al entrar en la aplicación desde el menú que se abre
al pulsar su nombre o avatar en la barra de navegación.

En Docker:

```bash
docker exec -it <contenedor> uv run --no-sync reset-password alex
```

Si el usuario no existe, el comando termina con código `1`; si la contraseña
indicada no cumple la longitud permitida (8–128 caracteres), termina con `2`.
