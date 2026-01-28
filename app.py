import pytz
import logging
from flask import Flask, render_template, redirect, url_for, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

from db import run_query, execute_command, get_connection

# -------------------------------------------------------------------
# LOGGING
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

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

    killed_count = 0

    for r in rows:
        username = str(r[user_idx]).upper()
        horas = int(r[horas_idx])
        event = str(r[event_idx]).lower()

        if username != "SYSTEM" and (horas >= 12 or "lock" in event or "mutex" in event):
            cmd = r[kill_idx].strip().rstrip(";")
            try:
                execute_command(cmd)
                killed_count += 1
                logger.info(f"Sessão encerrada: USER={username} | HORAS={horas}")
            except Exception as e:
                logger.error(f"Erro ao matar sessão {username}: {e}")

    logger.info(f"Total de sessões encerradas: {killed_count}")
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
    logger.info("Job automático iniciado")
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

    scheduler.add_job(monitor_sessions, IntervalTrigger(seconds=4))
    scheduler.add_job(scheduled_kill_all, IntervalTrigger(seconds=8))

    scheduler.start()
    logger.info("Scheduler iniciado")

    app.run(host="0.0.0.0", port=5001)
