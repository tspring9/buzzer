# Jeopardy Buzzer (Streamlit)

A small Streamlit app that functions as a Jeopardy-style buzzer: players can "buzz" with their name and an admin can see who buzzed first and reset rounds.

## Files to commit
- `app.py` — main Streamlit application
- `requirements.txt` — Python dependencies
- `.gitignore` — ignores local DB and secrets

## Run locally
1. Clone the repo:
   ```bash
   git clone https://github.com/<your-username>/buzzer.git
   cd buzzer
   ```
2. (Optional) Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS / Linux
   venv\Scripts\activate     # Windows
   pip install -r requirements.txt
   ```
3. Create a local secrets file (do NOT commit this):
   - Create the folder `.streamlit/` and a file `.streamlit/secrets.toml` with the content:
     ```toml
     ADMIN_PIN = "8675309"
     ```
4. Run Streamlit:
   ```bash
   streamlit run app.py
   ```

## Deploy to Streamlit Community Cloud
1. Push this repository to GitHub (e.g. `https://github.com/<your-username>/buzzer`).
2. Go to https://share.streamlit.io and create a new app.
3. Select your repo, branch (main), and the file `app.py`.
4. In the Streamlit app settings, open the "Secrets" panel and paste:
   ```toml
   ADMIN_PIN = "8675309"
   ```
   (Do not commit `.streamlit/secrets.toml` to the repo.)
5. Launch — the published app URL will be provided by Streamlit.

## Notes
- The app uses a local SQLite DB (`buzzer.db`) created in the repo root. On Streamlit Cloud this file persists for the app instance, but for production/multi-instance scenarios use a hosted DB.
- The Admin PIN in secrets is lightweight authentication only. For stronger security, integrate OAuth or other auth methods.