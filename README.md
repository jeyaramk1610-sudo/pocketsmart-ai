# PocketSmart AI — Flask Edition

This edition keeps the PocketSmart AI planning flow while avoiding the FastAPI/Pydantic native modules that can be blocked by Windows Enterprise Application Control.

## Features

- Register and Login
- Home Interior Planner
- Party Budget Planner
- Jewelry Planner with optional image upload
- Recommendation History stored in SQLite
- Optional Gemini AI enrichment through REST
- Simple browser UI
- No Node.js required
- No Docker required

## 1. Open the project

Extract the ZIP and open the extracted `PocketSmartAI_Flask` folder in VS Code.

Example:

`C:\Users\Acer\Projects\PocketSmartAI_Flask`

## 2. Create the virtual environment

In the VS Code terminal:

```powershell
py -3.13 -m venv .venv
```

You do NOT need to activate it.

## 3. Install packages

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

This uses the virtual environment's Python directly, so PowerShell activation is not required.

## 4. Start the project

```powershell
.\.venv\Scripts\python.exe app.py
```

You should see:

`PocketSmart AI running at http://127.0.0.1:5000`

Open that address in Chrome.

## 5. Optional Gemini AI

The project works without Gemini.

To enable AI enrichment:

1. Copy `.env.example` to `.env`.
2. Put your Gemini API key in `GEMINI_API_KEY`.
3. Start the app again.

The built-in recommendation engine remains available when the API key is empty or the API request fails.

## 6. Project routes

- `/` — Home
- `/register` — Register
- `/login` — Login
- `/dashboard` — Dashboard
- `/planner/home` — Home Interior Planner
- `/planner/party` — Party Budget Planner
- `/planner/jewelry` — Jewelry Planner
- `/history` — Recommendation History

## 7. If Windows blocks anything

This edition intentionally avoids packages such as `pydantic-core`, `httptools`, `watchfiles`, and other native FastAPI dependencies.

If your organization's Application Control policy also blocks Flask or another package, that is a Windows policy issue rather than a project-code issue; use an administrator-approved development environment.
