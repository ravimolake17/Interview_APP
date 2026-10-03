import asyncio, sys
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from starlette.concurrency import run_in_threadpool

COMBO = sys.argv[1]

async def test_docling():
    def worker():
        from docling.document_converter import DocumentConverter
        return DocumentConverter
    await run_in_threadpool(worker)
    print(COMBO, "OK")

async def workers():
    from agents.screening_agent.services.screening_worker_pool import get_worker_pool
    await get_worker_pool().start()

async def langgraph():
    from core.langgraph_runtime import init_langgraph_runtime
    await init_langgraph_runtime()

async def tts():
    from agents.interview_agent.tts_service import warmup_tts
    await asyncio.to_thread(warmup_tts)

async def main():
    steps = {"workers": workers, "langgraph": langgraph, "tts": tts}
    for part in COMBO.split("+"):
        if part in steps:
            await steps[part]()
    await test_docling()

asyncio.run(main())
