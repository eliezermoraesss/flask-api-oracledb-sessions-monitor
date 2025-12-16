from flask import Flask, render_template, redirect, url_for, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from db import run_query, execute_command, get_connection

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
     and TYPE<> 'BACKGROUND'
order by TYPE, logon_time
"""

# Cache global de resultados
last_result = {"cols": [], "rows": []}


def monitor_sessions():
    """Executa a query e atualiza o cache global."""
    global last_result
    cols, rows = run_query(QUERY)
    last_result = {"cols": cols, "rows": rows}

    # Exemplo opcional: Auto kill se >= 20 sessões
    # (deixe comentado se quiser só o botão manual)
    """
    if len(rows) >= 20:
        kill_index = cols.index("KILL")
        for r in rows:
            cmd = r[kill_index].strip().rstrip(";")
            execute_command(cmd)
    """


# Scheduler para monitoramento automático
scheduler = BackgroundScheduler()
scheduler.add_job(monitor_sessions, "interval", seconds=4)
scheduler.start()


@app.route("/")
def index():
    return render_template("index.html", data=last_result)


@app.route("/kill_all")
def kill_all():
    """Mata todas as sessões ativas (exceto SYSTEM)."""
    global last_result

    if not last_result["rows"]:
        monitor_sessions()  # Garante que os dados estejam atualizados

    cols = last_result["cols"]
    rows = last_result["rows"]

    if not rows:
        return redirect(url_for("index"))

    kill_idx = cols.index("KILL")
    user_idx = cols.index("USERNAME")

    killed_count = 0

    for r in rows:
        username = str(r[user_idx]).upper()
        if username != "SYSTEM":  # Protege usuário SYSTEM
            cmd = r[kill_idx].strip().rstrip(";")
            try:
                execute_command(cmd)
                killed_count += 1
            except Exception as e:
                print(f"Erro ao matar sessão de {username}: {e}")

    print(f"{killed_count} sessões foram encerradas.")
    return redirect(url_for("index"))


@app.route("/kill/<sid>/<serial>")
def kill_session(sid, serial):
    username = request.args.get("username", "").upper()

    if username == "SYSTEM":
        return jsonify({"error": "Sessão SYSTEM é protegida e não pode ser encerrada."}), 403

    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(f"ALTER SYSTEM KILL SESSION '{sid},{serial}'immediate")
        connection.commit()
        return redirect(url_for("index"))
    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
