# Interview test log
- Started: 2026-11-17 12:42:58
- Source: backend uvicorn (terminal 2)
- Baseline line: 111
- Focus: join, voice/face, mcq, stt-stream, transcribe, answer, speak, ValueError/empty_transcript

INFO:     127.0.0.1:55492 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK    
INFO:     127.0.0.1:62675 - "GET /api/interview/room/candidates/CAND-EC0A4158/runtime HTTP/1.1" 409 Conflict
INFO:     127.0.0.1:56688 - "GET /api/interview/agent6/candidates/CAND-EC0A4158/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:59856 - "GET /api/interview/blueprint/candidates/CAND-EC0A4158 HTTP/1.1" 200 OK
INFO:     127.0.0.1:56981 - "GET /api/interview/agent5/candidates/CAND-EC0A4158/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:63254 - "GET /api/interview/room/candidates/CAND-EC0A4158/runtime HTTP/1.1" 409 Conflict
INFO:     127.0.0.1:56983 - "GET /api/interview/agent6/candidates/CAND-EC0A4158/evaluations HTTP/1.1" 200 OK
INFO:     127.0.0.1:61501 - "GET /api/interview/agent4/candidates/CAND-EC0A4158/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:49191 - "GET /api/interview/agent7/candidates/CAND-EC0A4158/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:60602 - "GET /api/interview/agent4/candidates/CAND-EC0A4158/status HTTP/1.1" 200 OK

INFO:     127.0.0.1:53410 - "GET /api/hr/candidates/CAND-EC0A4158 HTTP/1.1" 404 Not Found 

