from logging.handlers import RotatingFileHandler

import pytz
import logging
from flask import Flask, render_template, redirect, url_for, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from db import run_query, execute_command, get_connection
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

APP_LOG_FILE = os.path.join(LOG_DIR, "oracle_kill_monitor.log")
SESSIONS_LOG_FILE = os.path.join(LOG_DIR, "sessions_snapshot.log")

# -------------------------------------------------------------------
# LOGGING
# -------------------------------------------------------------------
logger = logging.getLogger("oracle_kill_monitor")
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
)

file_handler = RotatingFileHandler(
    APP_LOG_FILE,
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding="utf-8"
)

file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

sessions_logger = logging.getLogger("sessions_snapshot")
sessions_logger.setLevel(logging.INFO)

sessions_handler = RotatingFileHandler(
    SESSIONS_LOG_FILE,
    maxBytes=50 * 1024 * 1024,  # 50MB
    backupCount=10,
    encoding="utf-8"
)

sessions_handler.setFormatter(logging.Formatter("%(message)s"))
sessions_logger.addHandler(sessions_handler)

# -------------------------------------------------------------------
# APP
# -------------------------------------------------------------------
app = Flask(__name__)

QUERY = """
select 'ALTER SYSTEM KILL SESSION '|| ''''||s.sid||','||s.serial#||'''' ||' IMMEDIATE' AS KILL,
       trunc(s.last_call_et/3600) horas,
       trunc(s.last_call_et/60) minutos,
       s.sid,
       s.serial#,
       s.username,
       s.machine,
       p.spid,
       s.osuser,
       s.client_info,
       s.EVENT,
       to_char(s.LOGON_TIME,'dd/mm/yyyy hh24:mi:ss') LOGON_TIME,
       sysdate HORA_ATUAL,
       s.program,
       s.machine
from gv$session s, gv$process p
WHERE s.paddr = p.addr
  and s.inst_id = p.inst_id
  and s.status='ACTIVE'
  and s.username is not null
  and TYPE <> 'BACKGROUND'
order by TYPE, logon_time
"""

# Cache global
last_result = {"cols": [], "rows": []}

# -------------------------------------------------------------------
# MONITORAMENTO
# -------------------------------------------------------------------
def monitor_sessions():
    global last_result
    try:
        cols, rows = run_query(QUERY)
        last_result = {"cols": cols, "rows": rows}

        logger.info(f"Sessões monitoradas: {len(rows)} ativas")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for r in rows:
            row = dict(zip(cols, r))
            sessions_logger.info(
                f"{timestamp} | "
                f"USER={row['USERNAME']} | "
                f"SID={row['SID']} | "
                f"SERIAL={row['SERIAL#']} | "
                f"HORAS={row['HORAS']} | "
                f"MINUTOS={row['MINUTOS']} | "
                f"CLIENT={row['CLIENT_INFO']} | "
                f"EVENT={row['EVENT']} | "
                f"MACHINE={row['MACHINE']}"
            )

    except Exception as e:
        logger.error(f"Erro ao executar monitor_sessions: {e}")

# -------------------------------------------------------------------
# KILL ALL AUTOMÁTICO
# -------------------------------------------------------------------
def kill_sessions_automatic():
    global last_result

    if not last_result["rows"]:
        monitor_sessions()

    cols = last_result["cols"]
    rows = last_result["rows"]

    kill_idx = cols.index("KILL")
    user_idx = cols.index("USERNAME")
    horas_idx = cols.index("HORAS")
    event_idx = cols.index("EVENT")
    client_idx = cols.index("CLIENT_INFO")
    machine_idx = cols.index("MACHINE")

    killed_count = 0

    for r in rows:
        username = str(r[user_idx]).upper()
        horas = int(r[horas_idx])
        event = str(r[event_idx]).upper()
        client = str(r[client_idx]).upper()
        machine = str(r[machine_idx]).upper()

        if (username != "SYSTEM" and machine != "localhost"
                and (horas >= 12
                    or "LOCK" in event or "MUTEX" in event
                    or not "SW.DEFAULT.SCHED" in client
                    or not "CONSOLID" in client)):
            cmd = r[kill_idx].strip().rstrip(";")

            try:
                execute_command(cmd)
                killed_count += 1
                logger.info(f"Sessão encerrada: "
                            f"USER = {username} | HORAS = {horas} | "
                            f"EVENT = {event} | CLIENT = {client} | CMD = {cmd} | MACHINE = {machine}")
            except Exception as e:
                logger.error(f"Erro ao matar sessão {username}: {e}")

    logger.info(f"Total de sessões encerradas: {killed_count}\n")
    return killed_count

# -------------------------------------------------------------------
# ROTAS
# -------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", data=last_result)

# -------------------------------------------------------------------
# KILL ALL MANUAL
# -------------------------------------------------------------------
@app.route("/kill_all")
def kill_all():
    kill_sessions_automatic()
    return redirect(url_for("index"))

# -------------------------------------------------------------------
# KILL INDIVIDUAL
# -------------------------------------------------------------------
@app.route("/kill/<sid>/<serial>")
def kill_session(sid, serial):
    username = request.args.get("username", "").upper()

    if username == "SYSTEM":
        logger.warning("Bloqueio de kill individual para SYSTEM")
        return jsonify({"error": "Sessão SYSTEM é protegida"}), 403

    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(f"ALTER SYSTEM KILL SESSION '{sid},{serial}' IMMEDIATE")
        connection.commit()
        logger.info(f"Kill individual executado SID={sid} SERIAL={serial}")
        return redirect(url_for("index"))
    except Exception as e:
        logger.error(f"Erro no kill individual SID={sid}: {e}")
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------------
# JOB AGENDADO
# -------------------------------------------------------------------
def scheduled_kill_all():
    logger.info("\nJob automático iniciado")
    try:
        kill_sessions_automatic()
    except Exception as e:
        logger.error(f"Erro no job automático: {e}")
    logger.info("Job automático finalizado")

# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Iniciando Oracle Kill Sessions Monitor")

    america_sp = pytz.timezone("America/Sao_Paulo")
    scheduler = BackgroundScheduler(timezone=america_sp)

    scheduler.add_job(monitor_sessions, IntervalTrigger(seconds=3))
    scheduler.add_job(scheduled_kill_all, IntervalTrigger(seconds=7))

    scheduler.start()
    logger.info("Scheduler iniciado")

    app.run(host="0.0.0.0", port=5001)
