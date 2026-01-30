
# 🧠 Oracle Kill Sessions Monitor

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-2.3-black?logo=flask)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-purple?logo=bootstrap)
![Oracle](https://img.shields.io/badge/Oracle-Database-red?logo=oracle)
![License](https://img.shields.io/badge/License-MIT-green)

---
![Demonstração3](assets/images/oracle-kill-session-03.gif)
![Demonstração1](assets/images/oracle-kill-session-01.gif)
![Demonstração2](assets/images/oracle-kill-session-02.gif)

## 📘 Sobre o Projeto

O **Oracle Kill Sessions Monitor** é uma aplicação web desenvolvida em **Python (Flask)** para **monitorar e gerenciar sessões ativas do banco de dados Oracle em tempo real**.

A ferramenta exibe todas as sessões de usuários conectados, mostrando informações como:
- SID, SERIAL, USERNAME, MACHINE, EVENT, TEMPO DE EXECUÇÃO, entre outras colunas;
- Possibilidade de **matar sessões individuais** ou **todas de uma vez**;
- Monitoramento automático a cada segundo via **APS Scheduler**, com **auto kill** quando o limite configurado é ultrapastado (por padrão, 20 sessões).

É ideal para **DBAs e equipes de suporte** que precisam visualizar e controlar sessões em tempo real sem depender de scripts SQL manuais.

---
## ⚙️ Funcionalidades Principais
✅ Monitoramento contín_*uo de sessões Oracle  
✅ Interface web para observabilidade em tempo real  
✅ Kill manual de sessões individuais (com proteções)  
✅ Kill automático baseado em regras técnicas  
✅ Proteção explícita para usuários SYS e SYSTEM  
✅ Proteção por MACHINE e CLIENT_INFO  
✅ Scheduler com regras por dia e horário  
✅ Logs técnicos detalhados para auditoria  
✅ Snapshot periódico das sessões para análise histórica  
✅ Rotação automática de logs (100MB)  
✅ Páginas dedicadas para visualização de logs no browser 
---


## 🧠 Regras Técnicas de Kill

Uma sessão **somente é encerrada automaticamente** se **TODAS** as condições abaixo forem atendidas:

- Usuário **≠ SYSTEM / SYS**
- MACHINE = `localhost`
- Não pertence a processos críticos (ex: backup, scheduler)
- Atende a pelo menos uma condição:
  - Tempo ativo ≥ 12 horas
  - Eventos contendo:
    - `LOCK`
    - `MUTEX`
    - `CPU QUANTUM`
    - `CACHE BUFFERS CHAINS`

---
## ⏰ Agendamentos (Scheduler)

### 🔄 Monitoramento de Sessões
- Executa a cada **4 segundos**
- Registra snapshot completo das sessões em log

### 🚨 Kill Automático
Executa apenas nos horários abaixo:

| Dia | Horário |
|----|--------|
| Segunda a Quinta | 08:00 às 18:00 |
| Sexta | 08:00 às 17:00 |
| Sábado | 08:00 às 12:00 |
| Domingo | ❌ Não executa |

---
## 🧩 Estrutura do Projeto

```
OracleKillSessionsMonitor/
│
├── app.py
├── db.py
├── requirements.txt
├── logs/
│   ├── oracle_kill_monitor.log
│   └── sessions_snapshot.log
│
├── templates/
│   ├── index.html
│   ├── logs.html
│   └── sessions_logs.html
│
├── static/
│   └── M.ico
│
└── README.md
```

---
## 📜 Logs & Auditoria

### 🔹 oracle_kill_monitor.log
- Execução dos jobs
- Sessões encerradas
- Erros e exceções
- Auditoria técnica

### 🔹 sessions_snapshot.log
- Snapshot contínuo das sessões
- Timestamp, SID, USER, EVENT, MACHINE
- Base para análise forense e capacity planning

---

## 🧰 Tecnologias Utilizadas

| Categoria | Tecnologias |
|------------|--------------|
| Linguagem  | **Python 3.11+** |
| Framework Web | **Flask 2.3** |
| Banco de Dados | **Oracle Database (cx_Oracle / oracledb)** |
| Interface | **Bootstrap 5.3** |
| Scheduler | **APScheduler** |
| Template Engine | **Jinja2** |

---

## 🚀 Como Executar o Projeto

### 1️⃣ Clonar o repositão
```bash
git clone https://github.com/SEU_USUARIO/OracleKillSessionsMonitor.git
cd OracleKillSessionsMonitor
```

### 2️⃣ Criar e ativar ambiente virtual
```bash
python -m venv .venv
# Windows
.venv\Scriptsctivate
# Linux / Mac
source .venv/bin/activate
```

### 3️⃣ Instalar dependências
```bash
pip install -r requirements.txt
```

### 4️⃣ Configurar variáveis de ambiente
Crie um arquivo **.env** na raiz com os dados da conexão Oracle:
```env
ORACLE_USER=system
ORACLE_PASSWORD=senha123
ORACLE_DSN=192.168.0.100:1521/xe
```

### 5️⃣ Executar o servidor Flask
```bash
python app.py
```

Acesse no navegador:  
👉 [http://localhost/5000](http://localhost/5000)

---

## 🖥️ Interface Web

A aplicação apresenta uma interface limpa e responsiva, com:
- Tabela de sessões Oracle
- Botão vermelho para matar todas as sessões
- Badge dinâmica mostrando o número de sessões (verde, amarela, vermelha conforme o volume)
- Auto refresh a cada 3 segundos

---

## 🧠 Lógica de Funcionamento

1. A cada segundo, o **APS Scheduler** executa a query em `gv$session` e `gv$process`;  
2. Os resultados são atualizados em cache (`last_result`);  
3. O template `index.html` renderiza esses dados;  
4. O botão **Kill** executa o comando `ALTER SYSTEM KILL SESSION '<sid>,<serial>' IMMEDIATE`;  
5. Se o total de sessões ≥ 20, o sistema executa o **auto kill** automaticamente;  
6. **Sessões com eventos contendo 'lock' são encerradas automaticamente, exceto as do usuário SYSTEM.**  

---

## 🧾 Exemplo de Query Usada

```sql
select 'ALTER SYSTEM KILL SESSION '|| ''''||s.sid||','||s.serial#||'''' ||' immediate;' AS KILL, 
       s.sql_address,
       s.inst_id,
       s.sid,
       s.serial#,
       s.username,
       p.spid,
       s.osuser,
       s.EVENT,
       trunc(s.last_call_et/3600) horas,
       trunc(s.last_call_et/60) minutos,
       s.machine,
       s.client_info,
       s.program,
       to_char(s.LOGON_TIME,'dd/mm/yyyy hh24:mi:ss') LOGON_TIME,
       sysdate HORA_ATUAL,
       s.PREV_SQL_ADDR,
       s.paddr,
       s.taddr,
       s.machine
from gv$session s, gv$process p
WHERE s.paddr = p.addr
     and s.inst_id = p.inst_id
     and s.status='ACTIVE'
     and s.username is not null
     and TYPE<> 'BACKGROUND'
order by TYPE,logon_time
```

---

## 📜 Licença

Este projeto está licenciado sob a **MIT License** – veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

## 🧩 Próximos Passos (Roadmap)

- [ ] Notificações automáticas via e-mail ou Telegram  
- [ ] Containerização com Docker  

---

⭐ Projeto desenvolvido para uso **real em produção**, com foco em **confiabilidade, controle e observabilidade**.

---

## 🧑‍💻 Autor

**Eliezer Moraes**  
Desenvolvedor de Software & Analista de Sistemas  

[![GitHub](https://img.shields.io/badge/GitHub-EliezerMoraes-black?logo=github)](https://github.com/eliezermoraes)  
[![LinkedIn](https://img.shields.io/badge/LinkedIn-EliezerMoraes-blue?logo=linkedin)](https://www.linkedin.com/in/eliezermoraes)
---