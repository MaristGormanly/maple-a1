from fastapi import FastAPI

app = FastAPI(title="MAPLE A1 Code Evaluator API")

@app.get("/api/v1/code-eval/health")
async def health_check():
    return {
        "success": True,
        "data": {
            "status": "ok"
        },
        "error": None,
        "metadata": {
            "module": "a1",
            "version": "1.0.0"
        }
    }