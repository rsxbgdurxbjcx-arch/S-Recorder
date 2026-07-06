#!/usr/bin/env python3
"""开发启动脚本 / Development startup script."""
import os
import sys
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "24136"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
