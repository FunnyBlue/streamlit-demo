# run_local.py
import os
import signal
import subprocess
import sys
import time
import requests
import webbrowser
import platform
from pathlib import Path

# ====== 1) Your Streamlit app code ======
app_code3 = r"""
import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit import session_state as ss

st.set_page_config(page_title="Doctor Review", page_icon="🩺", layout="wide")
st.title("Doctor Information Management (proposed updates)")
st.markdown("---")

REVIEWER = "Albert Yao"

# -------------------- Seed data + proposed changes --------------------
base_df = pd.DataFrame({
    "Name": [
        "Dr. Sarah Johnson", "Dr. Michael Chen", "Dr. Emily Rodriguez",
        "Dr. James Wilson", "Dr. Lisa Park"
    ],
    "Source Page": [
        "https://example.com/sarah-johnson",
        "https://example.com/michael-chen",
        "https://example.com/emily-rodriguez",
        "https://example.com/james-wilson",
        "https://example.com/lisa-park"
    ],
    "Address": [
        "123 Medical Center Dr, Boston, MA",
        "456 Healthcare Blvd, New York, NY",
        "789 Clinic Ave, Chicago, IL",
        "321 Hospital St, Los Angeles, CA",
        "654 Medical Plaza, Houston, TX"
    ],
    "Focus": ["Cardiology", "Neurology", "Pediatrics", "Orthopedics", "Dermatology"],
    "School Graduated": [
        "Harvard Medical School", "Johns Hopkins", "Stanford Medicine",
        "Yale School of Medicine", "UCLA Medical School"
    ],
    "Year": [2015, 2018, 2012, 2016, 2020],

    # Proposed NEW values (empty string/None means no change)
    "New Address": [
        "123 Medical Center Dr, Boston, MA",
        "999 5th Ave, New York, NY",
        "",
        "",
        "1200 Main St, Houston, TX"
    ],
    "New Focus": ["", "Neurosurgery", "", "", ""],
    "New School Graduated": ["", "", "Stanford School of Medicine", "", ""],
    "New Year": [None, None, None, 2018, None]
})

# Persist table across reruns
if "doctors" not in ss:
    ss.doctors = base_df.copy()
if "actions" not in ss:
    ss.actions = {}  # {doctor_name: "accepted" | "rejected"}
if "audit" not in ss:
    ss.audit = []    # list of dicts: {Time, Reviewer, Name, Action, Fields}

df = ss.doctors

# -------------------- Helpers --------------------
def _nonempty(v):
    if v is None:
        return False
    if isinstance(v, float) and pd.isna(v):
        return False
    return str(v).strip() != ""

def _proposed_pairs():
    # (base_col, new_col)
    return [
        ("Address","New Address"),
        ("Focus","New Focus"),
        ("School Graduated","New School Graduated"),
        ("Year","New Year"),
    ]

def get_changes(row):
    # Return list of (field, old, new) that actually change.
    changes = []
    for base_col, new_col in _proposed_pairs():
        new_val = row[new_col] if new_col in row.index else None
        if _nonempty(new_val) and new_val != row[base_col]:
            changes.append((base_col, row[base_col], new_val))
    return changes

def log_audit(name, action, fields_changed):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = {
        "Time": ts,
        "Reviewer": REVIEWER,
        "Name": name,
        "Action": action,
        "Fields": ", ".join(fields_changed) if fields_changed else "-"
    }
    ss.audit.append(entry)

def accept_row(idx):
    row = df.loc[idx]
    changes = get_changes(row)
    if not changes:
        st.toast(f"No changes to apply for {row['Name']}.")
        log_audit(row["Name"], "accepted (no-op)", [])
        return
    changed_fields = []
    for field, old, new in changes:
        df.at[idx, field] = new
        new_col = "New " + field if field != "School Graduated" else "New School Graduated"
        if new_col in df.columns:
            df.at[idx, new_col] = "" if isinstance(df.at[idx, new_col], str) else None
        changed_fields.append(field)
    ss.actions[row["Name"]] = "accepted"
    log_audit(row["Name"], "accepted", changed_fields)
    details = "; ".join([f"{f}: '{o}' -> '{n}'" for f, o, n in changes])
    st.toast(f"{row['Name']} updated. {details}")

def reject_row(idx):
    row = df.loc[idx]
    # Which fields had proposals?
    proposed_fields = []
    for base_col, new_col in _proposed_pairs():
        if new_col in df.columns and _nonempty(row[new_col]):
            proposed_fields.append(base_col)
            df.at[idx, new_col] = "" if isinstance(df.at[idx, new_col], str) else None
    ss.actions[row["Name"]] = "rejected"
    log_audit(row["Name"], "rejected", proposed_fields)
    if proposed_fields:
        st.toast(f"Rejected proposed changes for {row['Name']} ({', '.join(proposed_fields)}).")
    else:
        st.toast(f"Rejected for {row['Name']} (no proposed changes).")

# -------------------- Render table --------------------
st.markdown("### Review Table")

# Added 'Source' column
hdr = st.columns([2.0, 2.2, 2.6, 2.0, 2.4, 2.6, 1.1, 1.1])
for c, t in zip(
    hdr,
    ["Doctor", "Source", "Address", "Focus", "School / Year", "Proposed Changes", "Accept", "Reject"]
):
    c.markdown(f"**{t}**")

for i, row in df.iterrows():
    cols = st.columns([2.0, 2.2, 2.6, 2.0, 2.4, 2.6, 1.1, 1.1])

    with cols[0]:
        st.write(f"**{row['Name']}**")

    with cols[1]:
        url = row.get("Source Page", "")
        if _nonempty(url):
            st.markdown(f"[Open]({url})")
        else:
            st.caption("—")

    with cols[2]:
        st.write(row["Address"])

    with cols[3]:
        st.write(row["Focus"])

    with cols[4]:
        st.write(f"{row['School Graduated']}  ·  {row['Year']}")

    with cols[5]:
        changes = get_changes(row)
        if not changes:
            st.caption("-- No proposed changes --")
        else:
            for field, old, new in changes:
                st.markdown(f"- **{field}**: '{old}' → **'{new}'**")

    with cols[6]:
        if st.button("✅ Accept", key=f"accept_{i}"):
            accept_row(i)
            st.rerun()

    with cols[7]:
        if st.button("❌ Reject", key=f"reject_{i}"):
            reject_row(i)
            st.rerun()

st.divider()

# -------------------- Summary / Audit --------------------
st.subheader("Summary (this session)")
left, right = st.columns([3,2])

with left:
    # Actions rollup from quick banner
    if ss.actions:
        accepted = [n for n, a in ss.actions.items() if a.startswith("accepted")]
        rejected = [n for n, a in ss.actions.items() if a == "rejected"]
        c1, c2 = st.columns(2)
        with c1:
            st.success(f"Accepted ({len(accepted)}):")
            for n in accepted: st.write(f"- {n}")
        with c2:
            st.error(f"Rejected ({len(rejected)}):")
            for n in rejected: st.write(f"- {n}")
    else:
        st.caption("No actions yet.")

with right:
    # Download current view of the data
    st.download_button(
        "Download current table (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        "doctors_snapshot.csv",
        "text/csv"
    )

st.markdown("#### Audit log (who/what/when)")
if ss.audit:
    st.dataframe(pd.DataFrame(ss.audit), use_container_width=True, hide_index=True)
else:
    st.caption("No audit entries yet.")

# Clearers
c3, c4 = st.columns(2)
with c3:
    if st.button("Clear Session Actions"):
        ss.actions = {}
        st.toast("Cleared session actions.")
with c4:
    if st.button("Clear Audit Log"):
        ss.audit = []
        st.toast("Cleared audit log.")
"""

# ====== 2) Write app.py ======
Path("app.py").write_text(app_code3, encoding="utf-8")

# ====== 3) Kill anything already on :8501 (cross-platform best-effort) ======
def kill_on_port(port=8501):
    try:
        system = platform.system().lower()
        if "windows" in system:
            # netstat to find PID then taskkill
            out = subprocess.check_output(
                ["cmd", "/c", f"netstat -ano | findstr :{port}"], text=True, stderr=subprocess.DEVNULL
            )
            pids = set()
            for line in out.splitlines():
                parts = line.split()
                if parts and parts[-1].isdigit():
                    pids.add(parts[-1])
            for pid in pids:
                try:
                    subprocess.run(["taskkill", "/PID", pid, "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
        else:
            # Unix: lsof fallback
            pids = subprocess.check_output(
                ["bash", "-lc", f"lsof -t -i:{port}"], text=True
            ).strip().split()
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except Exception:
                    pass
    except Exception:
        pass

kill_on_port(8501)

# ====== 4) Start Streamlit locally ======
cmd = [
    "streamlit", "run", "app.py",
    "--server.port", "8501",
    "--server.address", "127.0.0.1",   # bind to localhost only
    "--server.headless", "true"
]
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

# ====== 5) Health check & open browser ======
def wait_health(url="http://127.0.0.1:8501/health", timeout=40):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

print("⏳ Starting Streamlit on http://127.0.0.1:8501 ...")
if not wait_health():
    print("❌ Streamlit failed to pass health check. Logs:")
    try:
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            print(line, end="")
    except Exception:
        pass
    sys.exit(1)

print("✅ Streamlit is up at: http://127.0.0.1:8501")
try:
    webbrowser.open("http://127.0.0.1:8501")
except Exception:
    pass

print("\n--- Streaming Streamlit logs (Ctrl+C to stop) ---")
try:
    while True:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.2)
            continue
        print(line, end="")
except KeyboardInterrupt:
    print("\n👋 Stopping...")
    try:
        proc.terminate()
    except Exception:
        pass