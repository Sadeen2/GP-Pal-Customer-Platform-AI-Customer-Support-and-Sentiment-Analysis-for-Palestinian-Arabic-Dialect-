# Frontend connected to FastAPI backend

ضع فولدر `frontend` بجانب فولدر `app` داخل مشروع الباك إند.

ثم أضف في `app/main.py`:

```python
from fastapi.staticfiles import StaticFiles

app.mount("/dashboard", StaticFiles(directory="frontend", html=True), name="dashboard")
```

شغل السيرفر:

```powershell
python -m uvicorn app.main:app --reload
```

افتح:

```text
http://127.0.0.1:8000/dashboard/
```

سجل دخولك بنفس مستخدم `/auth/login`. إذا ما عندك مستخدم، أنشئ واحد من Swagger عبر `/auth/register`.
