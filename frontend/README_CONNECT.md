# Frontend connected to FastAPI backend

Place the `frontend` folder next to the `app` folder inside your backend project.

Then add in `app/main.py`:

```python
from fastapi.staticfiles import StaticFiles

app.mount("/dashboard", StaticFiles(directory="frontend", html=True), name="dashboard")
```

Run the server:

```powershell
python -m uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/dashboard/
```

Sign in with the same user from `/auth/login`. If you don't have a user, create one from Swagger via `/auth/register`.
