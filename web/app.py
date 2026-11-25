"""牙科诊所诊疗信息平台 · 应用入口。

架构对应 4.10 图16：模块化单体，按业务域划分蓝图——
预约排班（staff.frontdesk）、临床病历（staff.doctor）、结算财务（staff.finance）、
运营报表（staff.manager / ops）、患者端（patient / api）。
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime

from flask import (Flask, jsonify, redirect, render_template, request,
                   session, url_for, Response)

import db
from db import money, now, today
from services import BusinessError, run_all_jobs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.secret_key = os.environ.get("DENTAL_SECRET", "dental-clinic-platform-demo-2024")
    app.jinja_env.filters["money"] = money
    app.jinja_env.filters["dt"] = lambda s: (s or "").replace("T", " ")[:16]
    app.jinja_env.filters["ymd"] = lambda s: (s or "")[:10]
    app.jinja_env.globals["today"] = today()
    app.jinja_env.globals["now_str"] = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    app.teardown_appcontext(db.close_db)

    from views.auth import bp as auth_bp
    from views.staff import bp as staff_bp
    from views.patient import bp as patient_bp
    from views.api import bp as api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(api_bp)

    @app.route("/")
    def index():
        if session.get("role"):
            return redirect(url_for("staff.home"))
        if session.get("patient_id"):
            return redirect(url_for("patient.home"))
        return redirect(url_for("auth.login"))

    @app.errorhandler(BusinessError)
    def handle_business_error(e: BusinessError):
        if request.path.startswith("/api/"):
            return jsonify({"code": e.status, "message": e.message, "data": e.data,
                            "trace_id": db.gen_no("T")}), e.status
        return render_template("error.html", status=e.status, message=e.message), e.status

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"code": 404, "message": "资源不存在"}), 404
        return render_template("error.html", status=404, message="页面不存在"), 404

    @app.after_request
    def add_headers(resp):
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        resp.headers["X-Platform-Version"] = "dental-clinic-1.0"
        return resp

    # 定时任务：进程内轻量调度（原型期替代 crontab，生产换成任务平台）
    if os.environ.get("DENTAL_NO_JOBS") != "1":
        _start_scheduler(app)

    return app


_scheduler_started = False


def _start_scheduler(app):
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    def loop():
        time.sleep(3)
        while True:
            try:
                with app.app_context():
                    run_all_jobs()
            except Exception as exc:          # 定时任务失败不阻塞服务
                app.logger.warning("scheduler error: %s", exc)
            time.sleep(600)

    threading.Thread(target=loop, daemon=True, name="dental-jobs").start()


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
