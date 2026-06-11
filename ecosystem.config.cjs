const fs = require("fs");
const path = require("path");

const uvicornCandidates = ["venv/bin/uvicorn", ".venv/bin/uvicorn"].map((p) =>
  path.join(__dirname, p)
);
const uvicornPath =
  uvicornCandidates.find((p) => fs.existsSync(p)) || uvicornCandidates[0];

/**
 * PM2 config for production (nginx → 127.0.0.1:8000).
 *
 *   cd ~/Survey-Backend && git pull
 *   source venv/bin/activate && pip install -r requirements.txt
 *   pm2 delete survey-backend 2>/dev/null || true
 *   pm2 start ecosystem.config.cjs && pm2 save
 */
module.exports = {
  apps: [
    {
      name: "survey-backend",
      cwd: __dirname,
      script: uvicornPath,
      args: "main:app --host 127.0.0.1 --port 8000",
      interpreter: "none",
      autorestart: true,
      max_restarts: 20,
      min_uptime: "5s",
      restart_delay: 3000,
      env: {
        RUN_DB_MIGRATIONS: "false",
      },
    },
  ],
};
