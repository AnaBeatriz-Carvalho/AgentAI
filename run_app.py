"""Small helper to run the Streamlit app using the new package layout.

Usage:
    python run_app.py

This will invoke Streamlit to run `src/app/app_streamlit.py`.
"""
import subprocess
import sys

def main():
    cmd = [sys.executable, "-m", "streamlit", "run", "src/app/app_streamlit.py"]
    print("Iniciando Streamlit:", " ".join(cmd))
    subprocess.run(cmd)

if __name__ == "__main__":
    main()
