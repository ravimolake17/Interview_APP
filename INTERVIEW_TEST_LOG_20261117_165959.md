# Interview test log

Recording started 2026-11-17 16:59:59

```
[17:08:12] 2026-11-17 17:08:12,173 | INFO | api.routes.interview | Interview join bootstrap candidate=CAND-3FB878C2 role=candidate elapsed_ms=768
[17:08:12] INFO:     127.0.0.1:56313 - "GET /api/interview/join/hnZEfJ18khSriv8GUVdW1Cbll_be0Ihab3nNNP2Dl24k9xcVxh5t3KD01usbIKIi HTTP/1.1" 200 OK
[17:08:12] 2026-11-17 17:08:12,262 | INFO | api.routes.interview | Interview join bootstrap candidate=CAND-3FB878C2 role=candidate elapsed_ms=48
[17:08:12] INFO:     127.0.0.1:56316 - "GET /api/interview/join/hnZEfJ18khSriv8GUVdW1Cbll_be0Ihab3nNNP2Dl24k9xcVxh5t3KD01usbIKIi HTTP/1.1" 200 OK
[17:08:12] INFO:     127.0.0.1:56318 - "GET /proctoring/?session_id=d08d3ece-2632-4780-af44-6f8235bfa027&token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1ZjQwZjI2ZS1mMTZlLTRlNjAtOGM0ZS0yYTM1M2RhMWNlZTkiLCJ0eXAiOiJjYW5kaWRhdGUiLCJpYXQiOjE3OTQ5MTU0OTIsImV4cCI6MTc5NDk1ODY5Miwic2Vzc2lvbl9pZCI6ImQwOGQzZWNlLTI2MzItNDc4MC1hZjQ0LTZmODIzNWJmYTAyNyIsInJyX2NhbmRpZGF0ZV9pZCI6IkNBTkQtM0ZCODc4QzIiLCJwYXJ0aWNpcGFudF9
[17:08:12] INFO:     127.0.0.1:56324 - "GET /api/runtime-config HTTP/1.1" 200 OK
[17:08:13] INFO:     127.0.0.1:50039 - "GET /api/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/state HTTP/1.1" 200 OK
[17:08:13] INFO:     127.0.0.1:61346 - "GET /api/interview/room/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/runtime HTTP/1.1" 410 Gone
[17:08:26] INFO:     127.0.0.1:58034 - "POST /api/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/device-check HTTP/1.1" 200 OK
[17:08:26] INFO:     127.0.0.1:64307 - "GET /api/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/voice/sentence HTTP/1.1" 200 OK
[17:08:29] INFO:     127.0.0.1:60265 - "POST /api/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/start HTTP/1.1" 200 OK
[17:08:29] INFO:     127.0.0.1:53247 - "GET /api/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/recording/status HTTP/1.1" 200 OK
[17:08:29] INFO:     127.0.0.1:56342 - "WebSocket /ws/sessions/d08d3ece-2632-4780-af44-6f8235bfa027?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1ZjQwZjI2ZS1mMTZlLTRlNjAtOGM0ZS0yYTM1M2RhMWNlZTkiLCJ0eXAiOiJjYW5kaWRhdGUiLCJpYXQiOjE3OTQ5MTU0OTIsImV4cCI6MTc5NDk1ODY5Miwic2Vzc2lvbl9pZCI6ImQwOGQzZWNlLTI2MzItNDc4MC1hZjQ0LTZmODIzNWJmYTAyNyIsInJyX2NhbmRpZGF0ZV9pZCI6IkNBTkQtM0ZCODc4QzIiLCJwYXJ0aWNpcGFudF9yb2xl
[17:08:29] INFO:     connection open
[17:08:29] INFO:     127.0.0.1:51812 - "GET /proctoring/pcm-worklet.js HTTP/1.1" 404 Not Found
[17:08:29] INFO:     127.0.0.1:51810 - "GET /api/interview/room/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/ai/session HTTP/1.1" 410 Gone
[17:08:29] INFO:     127.0.0.1:55731 - "POST /api/interview/room/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/ai/start HTTP/1.1" 410 Gone
[17:08:34] INFO:     127.0.0.1:49672 - "POST /api/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/recording/chunks HTTP/1.1" 200 OK
[17:08:35] INFO:     127.0.0.1:55973 - "POST /api/interview/room/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/leave HTTP/1.1" 410 Gone
[17:08:35] INFO:     connection closed
[17:08:35] INFO:     127.0.0.1:64214 - "POST /api/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/recording/chunks HTTP/1.1" 200 OK
[17:08:35] INFO:     127.0.0.1:57631 - "POST /api/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/recording/complete HTTP/1.1" 409 Conflict
[17:08:37] INFO:     127.0.0.1:63889 - "POST /api/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/recording/complete HTTP/1.1" 409 Conflict
[17:08:37] INFO:     127.0.0.1:59219 - "POST /api/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/recording/complete HTTP/1.1" 409 Conflict
[17:08:38] INFO:     127.0.0.1:55655 - "POST /api/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/recording/complete HTTP/1.1" 409 Conflict
[17:08:38] INFO:     127.0.0.1:52859 - "POST /api/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/recover-finalization HTTP/1.1" 409 Conflict
[17:08:47] 2026-11-17 17:08:46,807 | INFO | api.routes.interview | Interview join bootstrap candidate=CAND-3FB878C2 role=candidate elapsed_ms=113
[17:08:48] INFO:     127.0.0.1:50075 - "GET /api/interview/join/hnZEfJ18khSriv8GUVdW1Cbll_be0Ihab3nNNP2Dl24k9xcVxh5t3KD01usbIKIi HTTP/1.1" 200 OK
[17:08:48] 2026-11-17 17:08:47,277 | INFO | api.routes.interview | Interview join bootstrap candidate=CAND-3FB878C2 role=candidate elapsed_ms=65
[17:08:48] INFO:     127.0.0.1:50083 - "GET /api/interview/join/hnZEfJ18khSriv8GUVdW1Cbll_be0Ihab3nNNP2Dl24k9xcVxh5t3KD01usbIKIi HTTP/1.1" 200 OK
[17:08:48] INFO:     127.0.0.1:50085 - "GET /proctoring/?session_id=d08d3ece-2632-4780-af44-6f8235bfa027&token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1ZjQwZjI2ZS1mMTZlLTRlNjAtOGM0ZS0yYTM1M2RhMWNlZTkiLCJ0eXAiOiJjYW5kaWRhdGUiLCJpYXQiOjE3OTQ5MTU1MjcsImV4cCI6MTc5NDk1ODcyNywic2Vzc2lvbl9pZCI6ImQwOGQzZWNlLTI2MzItNDc4MC1hZjQ0LTZmODIzNWJmYTAyNyIsInJyX2NhbmRpZGF0ZV9pZCI6IkNBTkQtM0ZCODc4QzIiLCJwYXJ0aWNpcGFudF9
[17:08:48] INFO:     127.0.0.1:50087 - "GET /api/runtime-config HTTP/1.1" 200 OK
[17:08:48] INFO:     127.0.0.1:50089 - "GET /api/sessions/d08d3ece-2632-4780-af44-6f8235bfa027/state HTTP/1.1" 200 OK
[17:08:59] 2026-11-17 17:08:58,632 | WARNING | passlib.handlers.bcrypt | (trapped) error reading bcrypt version
[17:08:59] Traceback (most recent call last):
[17:08:59]   File "C:\Users\ravi.molake\Downloads\Interview_Agentic_AI\backend\venv\Lib\site-packages\passlib\handlers\bcrypt.py", line 620, in _load_backend_mixin
[17:08:59]     version = _bcrypt.__about__.__version__
[17:08:59]               ^^^^^^^^^^^^^^^^^
[17:08:59] AttributeError: module 'bcrypt' has no attribute '__about__'
[17:09:00] INFO:     127.0.0.1:61383 - "POST /api/auth/login HTTP/1.1" 200 OK
[17:09:00] INFO:     127.0.0.1:61388 - "GET /api/companies HTTP/1.1" 200 OK
[17:09:00] INFO:     127.0.0.1:62740 - "GET /api/settings HTTP/1.1" 200 OK
[17:09:00] INFO:     127.0.0.1:62745 - "GET /api/departments HTTP/1.1" 200 OK
[17:09:00] INFO:     127.0.0.1:62743 - "GET /api/jobs HTTP/1.1" 200 OK
[17:09:01] INFO:     127.0.0.1:62746 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:09:01] INFO:     127.0.0.1:62742 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:09:01] INFO:     127.0.0.1:62741 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:09:04] INFO:     127.0.0.1:51997 - "GET /api/departments HTTP/1.1" 200 OK
[17:09:04] INFO:     127.0.0.1:51994 - "GET /api/jobs HTTP/1.1" 200 OK
[17:09:04] INFO:     127.0.0.1:51995 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:09:04] INFO:     127.0.0.1:51991 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:09:04] INFO:     127.0.0.1:51990 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:09:05] INFO:     127.0.0.1:65499 - "GET /api/hr/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:09:05] INFO:     127.0.0.1:55258 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:05] INFO:     127.0.0.1:55257 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[17:09:05] INFO:     127.0.0.1:50070 - "GET /api/interview/agent7/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:05] INFO:     127.0.0.1:63751 - "GET /api/hr/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:09:05] INFO:     127.0.0.1:55254 - "GET /api/interview/blueprint/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:09:05] INFO:     127.0.0.1:55255 - "GET /api/interview/agent4/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:05] INFO:     127.0.0.1:50275 - "GET /api/interview/agent5/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:05] INFO:     127.0.0.1:55259 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/evaluations HTTP/1.1" 200 OK
[17:09:05] INFO:     127.0.0.1:51888 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[17:09:05] INFO:     127.0.0.1:65036 - "GET /api/interview/room/candidates/CAND-3FB878C2/runtime HTTP/1.1" 410 Gone
[17:09:06] INFO:     127.0.0.1:53342 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:06] INFO:     127.0.0.1:52553 - "GET /api/interview/agent7/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:06] INFO:     127.0.0.1:51140 - "GET /api/interview/agent5/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:06] INFO:     127.0.0.1:49862 - "GET /api/interview/agent4/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:06] INFO:     127.0.0.1:59599 - "GET /api/interview/blueprint/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:09:06] INFO:     127.0.0.1:62268 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/evaluations HTTP/1.1" 200 OK
[17:09:06] INFO:     127.0.0.1:64405 - "GET /api/hr/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:09:06] INFO:     127.0.0.1:57143 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[17:09:06] INFO:     127.0.0.1:57145 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/evaluations HTTP/1.1" 200 OK
[17:09:06] INFO:     127.0.0.1:57146 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:06] INFO:     127.0.0.1:57142 - "GET /api/interview/blueprint/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:09:06] INFO:     127.0.0.1:60410 - "GET /api/interview/agent5/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:06] INFO:     127.0.0.1:61810 - "GET /api/hr/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:09:06] INFO:     127.0.0.1:57144 - "GET /api/interview/agent4/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:07] INFO:     127.0.0.1:63672 - "GET /api/interview/agent7/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:07] INFO:     127.0.0.1:49679 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[17:09:07] INFO:     127.0.0.1:49681 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/evaluations HTTP/1.1" 200 OK
[17:09:07] INFO:     127.0.0.1:49675 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:07] INFO:     127.0.0.1:49674 - "GET /api/interview/blueprint/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:09:07] INFO:     127.0.0.1:49680 - "GET /api/interview/agent4/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:07] INFO:     127.0.0.1:61441 - "GET /api/interview/agent7/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:07] INFO:     127.0.0.1:53586 - "GET /api/interview/agent5/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:09:07] E0000 00:00:1794915547.232053   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T11:44:07.170553+00:00
[17:09:07] === Source Location Trace: === 
[17:09:07] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[17:09:35] INFO:     127.0.0.1:60853 - "GET /api/auth/me HTTP/1.1" 200 OK
[17:09:35] INFO:     127.0.0.1:60856 - "GET /api/departments HTTP/1.1" 200 OK
[17:09:35] INFO:     127.0.0.1:60857 - "GET /api/jobs HTTP/1.1" 200 OK
[17:09:35] INFO:     127.0.0.1:60858 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:09:35] INFO:     127.0.0.1:60626 - "GET /api/hr/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:09:35] INFO:     127.0.0.1:60855 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:09:35] INFO:     127.0.0.1:60854 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:09:45] INFO:     127.0.0.1:59612 - "GET /api/jobs HTTP/1.1" 200 OK
[17:09:45] INFO:     127.0.0.1:59613 - "GET /api/departments HTTP/1.1" 200 OK
[17:09:45] INFO:     127.0.0.1:59615 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:09:45] INFO:     127.0.0.1:59611 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:09:45] INFO:     127.0.0.1:59610 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:09:48] INFO:     127.0.0.1:64251 - "GET /api/departments HTTP/1.1" 200 OK
[17:09:48] INFO:     127.0.0.1:64253 - "GET /api/jobs HTTP/1.1" 200 OK
[17:09:48] INFO:     127.0.0.1:64252 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:09:48] INFO:     127.0.0.1:64250 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:09:48] INFO:     127.0.0.1:64249 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:10:01] INFO:     127.0.0.1:56499 - "GET /api/departments HTTP/1.1" 200 OK
[17:10:01] INFO:     127.0.0.1:56498 - "GET /api/jobs HTTP/1.1" 200 OK
[17:10:01] INFO:     127.0.0.1:56500 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:10:01] INFO:     127.0.0.1:56497 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:10:01] INFO:     127.0.0.1:56495 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:10:03] INFO:     127.0.0.1:61361 - "POST /extract/async HTTP/1.1" 202 Accepted
[17:10:03] 2026-11-17 17:10:02,298 | INFO | agents.screening_agent.services.docling_extractor | Docling PDF extraction started (OCR mode: auto)
[17:10:03] INFO:     127.0.0.1:54211 - "GET /api/candidates/evaluate/jobs/5b065fda-3ac4-4580-8127-abcf479283ac HTTP/1.1" 200 OK
[17:10:05] INFO:     127.0.0.1:65292 - "GET /api/candidates/evaluate/jobs/5b065fda-3ac4-4580-8127-abcf479283ac HTTP/1.1" 200 OK
[17:10:06] 2026-11-17 17:10:05,836 | INFO | docling.datamodel.document | detected formats: [<InputFormat.PDF: 'pdf'>]
[17:10:06] 2026-11-17 17:10:05,918 | INFO | docling.document_converter | Going to convert document batch...
[17:10:06] 2026-11-17 17:10:05,918 | INFO | docling.document_converter | Initializing pipeline for StandardPdfPipeline with options hash 5b39d33c48cfc35453e7c3ec8c50b497
[17:10:06] 2026-11-17 17:10:05,984 | INFO | docling.models.factories.base_factory | Loading plugin 'docling_defaults'
[17:10:06] 2026-11-17 17:10:05,993 | INFO | docling.models.factories | Registered picture descriptions: ['picture_description_vlm_engine', 'vlm', 'api']
[17:10:06] 2026-11-17 17:10:06,034 | INFO | docling.models.factories.base_factory | Loading plugin 'docling_defaults'
[17:10:06] 2026-11-17 17:10:06,097 | INFO | docling.models.factories | Registered ocr engines: ['auto', 'easyocr', 'kserve_v2_ocr', 'nemotron-ocr', 'ocrmac', 'rapidocr', 'tesserocr', 'tesseract']
[17:10:06] 2026-11-17 17:10:06,151 | INFO | docling.models.factories.base_factory | Loading plugin 'docling_defaults'
[17:10:06] 2026-11-17 17:10:06,168 | INFO | docling.models.factories | Registered layout engines: ['layout_object_detection', 'docling_layout_default', 'docling_experimental_table_crops_layout']
[17:10:06] 2026-11-17 17:10:06,186 | INFO | docling.utils.accelerator_utils | Accelerator device: 'cpu'
[17:10:07] INFO:     127.0.0.1:51519 - "GET /api/candidates/evaluate/jobs/5b065fda-3ac4-4580-8127-abcf479283ac HTTP/1.1" 200 OK
[17:10:08] E0000 00:00:1794915607.247177   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T11:44:07.170553+00:00
[17:10:08] === Source Location Trace: === 
[17:10:08] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[17:10:08] 2026-11-17 17:10:07,408 | INFO | docling.models.factories.base_factory | Loading plugin 'docling_defaults'
[17:10:08] 2026-11-17 17:10:07,422 | INFO | docling.models.factories | Registered table structure engines: ['docling_tableformer', 'docling_tableformer_v2', 'granite_vision_table']
[17:10:08] 2026-11-17 17:10:07,827 | INFO | docling.utils.accelerator_utils | Accelerator device: 'cpu'
[17:10:09] INFO:     127.0.0.1:50573 - "GET /api/candidates/evaluate/jobs/5b065fda-3ac4-4580-8127-abcf479283ac HTTP/1.1" 200 OK
[17:10:09] 2026-11-17 17:10:08,890 | INFO | docling.pipeline.base_pipeline | Processing document 9973b649f73347b5b4c0adad2aa73a16.pdf
[17:10:11] INFO:     127.0.0.1:53980 - "GET /api/candidates/evaluate/jobs/5b065fda-3ac4-4580-8127-abcf479283ac HTTP/1.1" 200 OK
[17:10:13] INFO:     127.0.0.1:60799 - "GET /api/candidates/evaluate/jobs/5b065fda-3ac4-4580-8127-abcf479283ac HTTP/1.1" 200 OK
[17:10:15] INFO:     127.0.0.1:50710 - "GET /api/departments HTTP/1.1" 200 OK
[17:10:15] INFO:     127.0.0.1:50708 - "GET /api/jobs HTTP/1.1" 200 OK
[17:10:15] INFO:     127.0.0.1:62171 - "GET /api/candidates/evaluate/jobs/5b065fda-3ac4-4580-8127-abcf479283ac HTTP/1.1" 200 OK
[17:10:15] INFO:     127.0.0.1:50709 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:10:15] INFO:     127.0.0.1:50707 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:10:15] INFO:     127.0.0.1:50706 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:10:16] 2026-11-17 17:10:15,968 | INFO | docling.document_converter | Finished converting document 9973b649f73347b5b4c0adad2aa73a16.pdf in 10.17 sec.
[17:10:16] 2026-11-17 17:10:16,134 | INFO | agents.screening_agent.services.docling_extractor | PDF conversion succeeded using the embedded text layer
[17:10:16] 2026-11-17 17:10:16,173 | WARNING | agents.screening_agent.services.screening_worker_pool | Screening job 5b065fda-3ac4-4580-8127-abcf479283ac blocked: This candidate (ravi.molake@rrglobal.com) has already been screened at RR Kabel. Re-screening the same resume is not allowed.
[17:10:17] INFO:     127.0.0.1:49732 - "GET /api/candidates/evaluate/jobs/5b065fda-3ac4-4580-8127-abcf479283ac HTTP/1.1" 200 OK
[17:10:29] INFO:     127.0.0.1:62923 - "GET /api/departments HTTP/1.1" 200 OK
[17:10:29] INFO:     127.0.0.1:62921 - "GET /api/jobs HTTP/1.1" 200 OK
[17:10:29] INFO:     127.0.0.1:62924 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:10:29] INFO:     127.0.0.1:62920 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:10:29] INFO:     127.0.0.1:62919 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:10:31] INFO:     127.0.0.1:50983 - "GET /api/auth/me HTTP/1.1" 200 OK
[17:10:31] INFO:     127.0.0.1:50986 - "GET /api/auth/me HTTP/1.1" 200 OK
[17:10:31] INFO:     127.0.0.1:50988 - "GET /api/companies HTTP/1.1" 200 OK
[17:10:32] INFO:     127.0.0.1:62139 - "GET /api/settings HTTP/1.1" 200 OK
[17:10:32] INFO:     127.0.0.1:62147 - "GET /api/departments HTTP/1.1" 200 OK
[17:10:32] INFO:     127.0.0.1:62146 - "GET /api/jobs HTTP/1.1" 200 OK
[17:10:32] INFO:     127.0.0.1:62148 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:10:32] INFO:     127.0.0.1:62145 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:10:32] INFO:     127.0.0.1:62144 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:10:33] INFO:     127.0.0.1:64977 - "GET /api/hr/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:10:33] INFO:     127.0.0.1:50909 - "GET /api/hr/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:10:33] INFO:     127.0.0.1:55060 - "GET /api/interview/agent7/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:33] INFO:     127.0.0.1:60675 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:56634 - "GET /api/interview/agent5/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:60678 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/evaluations HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:60677 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:60676 - "GET /api/interview/agent4/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:58198 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:60674 - "GET /api/interview/blueprint/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:58387 - "GET /api/interview/agent5/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:57083 - "GET /api/hr/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:55400 - "GET /api/interview/agent7/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:52661 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/evaluations HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:61691 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:53894 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:53896 - "GET /api/interview/agent4/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:56674 - "GET /api/hr/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:54536 - "GET /api/interview/blueprint/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:57244 - "GET /api/interview/agent7/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:62415 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/evaluations HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:50133 - "GET /api/interview/agent5/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:62111 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:50025 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:56462 - "GET /api/interview/blueprint/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:59986 - "GET /api/interview/agent4/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:64422 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/evaluations HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:64420 - "GET /api/interview/agent7/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:59575 - "GET /api/interview/agent5/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:59577 - "GET /api/interview/agent6/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:56609 - "GET /api/interview/blueprint/candidates/CAND-3FB878C2 HTTP/1.1" 200 OK
[17:10:34] INFO:     127.0.0.1:63286 - "GET /api/interview/agent4/candidates/CAND-3FB878C2/status HTTP/1.1" 200 OK
[17:10:51] INFO:     127.0.0.1:56029 - "GET /api/auth/me HTTP/1.1" 200 OK
[17:10:51] INFO:     127.0.0.1:53669 - "GET /api/departments HTTP/1.1" 200 OK
[17:10:51] INFO:     127.0.0.1:65362 - "GET /api/hr/candidates/CAND-3FB878C2 HTTP/1.1" 404 Not Found
[17:10:51] INFO:     127.0.0.1:53668 - "GET /api/jobs HTTP/1.1" 200 OK
[17:10:51] INFO:     127.0.0.1:53667 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:10:51] INFO:     127.0.0.1:53661 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:10:51] INFO:     127.0.0.1:53670 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:11:02] INFO:     127.0.0.1:56676 - "GET /api/departments HTTP/1.1" 200 OK
[17:11:02] INFO:     127.0.0.1:56675 - "GET /api/jobs HTTP/1.1" 200 OK
[17:11:02] INFO:     127.0.0.1:56673 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:11:02] INFO:     127.0.0.1:56672 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:11:02] INFO:     127.0.0.1:56670 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:11:08] INFO:     127.0.0.1:55335 - "GET /api/departments HTTP/1.1" 200 OK
[17:11:08] INFO:     127.0.0.1:55334 - "GET /api/jobs HTTP/1.1" 200 OK
[17:11:08] E0000 00:00:1794915667.248377   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T11:44:07.170553+00:00
[17:11:08] === Source Location Trace: === 
[17:11:08] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[17:11:08] INFO:     127.0.0.1:55333 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:11:08] INFO:     127.0.0.1:55328 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:11:08] INFO:     127.0.0.1:55336 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:11:09] INFO:     127.0.0.1:51035 - "POST /extract/async HTTP/1.1" 202 Accepted
[17:11:09] 2026-11-17 17:11:08,334 | INFO | agents.screening_agent.services.docling_extractor | Docling PDF extraction started (OCR mode: auto)
[17:11:09] INFO:     127.0.0.1:50397 - "GET /api/candidates/evaluate/jobs/89f1fa1e-2cb6-4874-acc2-04f1e6536198 HTTP/1.1" 200 OK
[17:11:09] 2026-11-17 17:11:08,384 | INFO | docling.datamodel.document | detected formats: [<InputFormat.PDF: 'pdf'>]
[17:11:09] 2026-11-17 17:11:08,384 | INFO | docling.document_converter | Going to convert document batch...
[17:11:09] 2026-11-17 17:11:08,384 | INFO | docling.pipeline.base_pipeline | Processing document bd8ba903c9c445a2b82893f114734c8a.pdf
[17:11:11] INFO:     127.0.0.1:57635 - "GET /api/candidates/evaluate/jobs/89f1fa1e-2cb6-4874-acc2-04f1e6536198 HTTP/1.1" 200 OK
[17:11:13] INFO:     127.0.0.1:58004 - "GET /api/candidates/evaluate/jobs/89f1fa1e-2cb6-4874-acc2-04f1e6536198 HTTP/1.1" 200 OK
[17:11:15] INFO:     127.0.0.1:53594 - "GET /api/candidates/evaluate/jobs/89f1fa1e-2cb6-4874-acc2-04f1e6536198 HTTP/1.1" 200 OK
[17:11:15] 2026-11-17 17:11:14,869 | INFO | docling.document_converter | Finished converting document bd8ba903c9c445a2b82893f114734c8a.pdf in 6.53 sec.
[17:11:15] 2026-11-17 17:11:14,975 | INFO | agents.screening_agent.services.docling_extractor | PDF conversion succeeded using the embedded text layer
[17:11:15] 2026-11-17 17:11:15,250 | INFO | agents.shared.azure_http | Azure httpx client ready (name=openai, max_connections=32)
[17:11:17] INFO:     127.0.0.1:61870 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:11:17] INFO:     127.0.0.1:61874 - "GET /api/departments HTTP/1.1" 200 OK
[17:11:17] INFO:     127.0.0.1:61872 - "GET /api/jobs HTTP/1.1" 200 OK
[17:11:17] INFO:     127.0.0.1:50452 - "GET /api/candidates/evaluate/jobs/89f1fa1e-2cb6-4874-acc2-04f1e6536198 HTTP/1.1" 200 OK
[17:11:17] INFO:     127.0.0.1:61873 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:11:17] INFO:     127.0.0.1:61871 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:11:19] INFO:     127.0.0.1:56115 - "GET /api/candidates/evaluate/jobs/89f1fa1e-2cb6-4874-acc2-04f1e6536198 HTTP/1.1" 200 OK
[17:11:21] INFO:     127.0.0.1:61303 - "GET /api/candidates/evaluate/jobs/89f1fa1e-2cb6-4874-acc2-04f1e6536198 HTTP/1.1" 200 OK
[17:11:23] INFO:     127.0.0.1:52554 - "GET /api/candidates/evaluate/jobs/89f1fa1e-2cb6-4874-acc2-04f1e6536198 HTTP/1.1" 200 OK
[17:11:24] 2026-11-17 17:11:24,517 | INFO | httpx | HTTP Request: POST https://interview-openai-foundr-resource.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-10-21 "HTTP/1.1 200 OK"
[17:11:24] 2026-11-17 17:11:24,613 | INFO | agents.screening_agent.services.screening_job_runner | Extract job 89f1fa1e-2cb6-4874-acc2-04f1e6536198 parsed Ravi_Molake_Resume_office 1.pdf; scoring job 8c411a04-4e20-4daf-80bc-90bffb35fd77 queued
[17:11:25] INFO:     127.0.0.1:58925 - "GET /api/candidates/evaluate/jobs/89f1fa1e-2cb6-4874-acc2-04f1e6536198 HTTP/1.1" 200 OK
[17:11:25] INFO:     127.0.0.1:53995 - "GET /api/candidates/evaluate/jobs/8c411a04-4e20-4daf-80bc-90bffb35fd77 HTTP/1.1" 200 OK
[17:11:27] INFO:     127.0.0.1:57266 - "GET /api/candidates/evaluate/jobs/8c411a04-4e20-4daf-80bc-90bffb35fd77 HTTP/1.1" 200 OK
[17:11:28] 2026-11-17 17:11:28,744 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='Python' | Resume='Python' | Similarity=1.000 | Status=Perfect Match | Level=EXACT_MATCH | Method=exact
[17:11:28] 2026-11-17 17:11:28,748 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='Object-Oriented Programming (OOP)' | Resume='Object-Oriented Programming' | Similarity=0.926 | Status=Perfect Match | Level=STRONG_SEMANTIC_MATCH | Method=semantic
[17:11:28] 2026-11-17 17:11:28,748 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='FastAPI' | Resume='FastAPI' | Similarity=1.000 | Status=Perfect Match | Level=EXACT_MATCH | Method=exact
[17:11:28] 2026-11-17 17:11:28,748 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='Flask' | Resume='Flask' | Similarity=1.000 | Status=Perfect Match | Level=EXACT_MATCH | Method=exact
[17:11:28] 2026-11-17 17:11:28,748 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='TensorFlow' | Resume='TensorFlow' | Similarity=1.000 | Status=Perfect Match | Level=EXACT_MATCH | Method=exact
[17:11:28] 2026-11-17 17:11:28,748 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='PyTorch' | Resume='PyTorch' | Similarity=1.000 | Status=Perfect Match | Level=EXACT_MATCH | Method=exact
[17:11:28] 2026-11-17 17:11:28,748 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='NumPy' | Resume='NumPy' | Similarity=1.000 | Status=Perfect Match | Level=EXACT_MATCH | Method=exact
[17:11:28] 2026-11-17 17:11:28,756 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='Machine Learning Algorithms' | Resume='Machine Learning' | Similarity=0.937 | Status=Perfect Match | Level=STRONG_SEMANTIC_MATCH | Method=semantic
[17:11:45] INFO:     127.0.0.1:59468 - "GET /api/candidates/evaluate/jobs/8c411a04-4e20-4daf-80bc-90bffb35fd77 HTTP/1.1" 200 OK
[17:11:45] 2026-11-17 17:11:44,623 | INFO | services.screening_integration_service | Re-screened existing candidate CAND-26907EAD for same JD — preserved interview/proctoring history
[17:11:45] INFO:     127.0.0.1:53429 - "GET /api/departments HTTP/1.1" 200 OK
[17:11:45] 2026-11-17 17:11:44,694 | INFO | agents.scheduler_agent.nodes | Scheduling invite link for CAND-26907EAD: http://localhost:5173/schedule/7a73811d-0c2c-46c1-a461-a4125e755041
[17:11:45] INFO:     127.0.0.1:53428 - "GET /api/jobs HTTP/1.1" 200 OK
[17:11:45] INFO:     127.0.0.1:53430 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:11:45] INFO:     127.0.0.1:53427 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:11:45] INFO:     127.0.0.1:53423 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:11:47] INFO:     127.0.0.1:55552 - "GET /api/departments HTTP/1.1" 200 OK
[17:11:47] INFO:     127.0.0.1:55548 - "GET /api/jobs HTTP/1.1" 200 OK
[17:11:47] INFO:     127.0.0.1:63903 - "GET /api/candidates/evaluate/jobs/8c411a04-4e20-4daf-80bc-90bffb35fd77 HTTP/1.1" 200 OK
[17:11:47] INFO:     127.0.0.1:55547 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:11:47] INFO:     127.0.0.1:55543 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:11:47] INFO:     127.0.0.1:55554 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:11:48] 2026-11-17 17:11:47,200 | INFO | agents.scheduler_agent.nodes | Interview slots synced: created=0 removed=8 total=927
[17:11:48] 2026-11-17 17:11:48,085 | INFO | services.email_service | Email sent via SMTP to=ravi.molake@rrglobal.com subject=RR Kabel | Your Resume Has Been Shortlisted
[17:11:49] 2026-11-17 17:11:48,883 | INFO | services.screening_integration_service | Shortlisted candidate CAND-26907EAD (ravi.molake@rrglobal.com) — invite sent, token=7a73811d-0c2c-46c1-a461-a4125e755041
[17:11:49] INFO:     127.0.0.1:61929 - "GET /api/candidates/evaluate/jobs/8c411a04-4e20-4daf-80bc-90bffb35fd77 HTTP/1.1" 200 OK
[17:11:50] INFO:     127.0.0.1:60360 - "GET /api/departments HTTP/1.1" 200 OK
[17:11:50] INFO:     127.0.0.1:60359 - "GET /api/jobs HTTP/1.1" 200 OK
[17:11:50] INFO:     127.0.0.1:60357 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:11:50] INFO:     127.0.0.1:60361 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:11:50] INFO:     127.0.0.1:60358 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:12:02] INFO:     127.0.0.1:52176 - "GET /api/departments HTTP/1.1" 200 OK
[17:12:02] INFO:     127.0.0.1:52173 - "GET /api/jobs HTTP/1.1" 200 OK
[17:12:02] INFO:     127.0.0.1:52177 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:12:02] INFO:     127.0.0.1:52172 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:12:02] INFO:     127.0.0.1:52169 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:12:07] E0000 00:00:1794915727.260759   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T11:44:07.170553+00:00
[17:12:07] === Source Location Trace: === 
[17:12:07] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[17:12:15] INFO:     127.0.0.1:51506 - "GET /api/auth/me HTTP/1.1" 200 OK
[17:12:15] INFO:     127.0.0.1:51510 - "GET /api/auth/me HTTP/1.1" 200 OK
[17:12:15] INFO:     127.0.0.1:51512 - "GET /api/companies HTTP/1.1" 200 OK
[17:12:15] INFO:     127.0.0.1:56588 - "GET /api/settings HTTP/1.1" 200 OK
[17:12:16] INFO:     127.0.0.1:56596 - "GET /api/departments HTTP/1.1" 200 OK
[17:12:16] INFO:     127.0.0.1:56594 - "GET /api/jobs HTTP/1.1" 200 OK
[17:12:16] INFO:     127.0.0.1:54030 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:12:16] INFO:     127.0.0.1:56593 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:12:16] INFO:     127.0.0.1:56592 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:12:17] INFO:     127.0.0.1:51505 - "GET /api/interview/token/7a73811d-0c2c-46c1-a461-a4125e755041 HTTP/1.1" 200 OK
[17:12:18] INFO:     127.0.0.1:50853 - "GET /api/interview/token/7a73811d-0c2c-46c1-a461-a4125e755041 HTTP/1.1" 200 OK
[17:12:30] INFO:     127.0.0.1:65524 - "GET /api/departments HTTP/1.1" 200 OK
[17:12:30] INFO:     127.0.0.1:65521 - "GET /api/jobs HTTP/1.1" 200 OK
[17:12:30] INFO:     127.0.0.1:65525 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:12:30] INFO:     127.0.0.1:65520 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:12:30] INFO:     127.0.0.1:65519 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:12:46] INFO:     127.0.0.1:60949 - "GET /api/departments HTTP/1.1" 200 OK
[17:12:46] INFO:     127.0.0.1:60947 - "GET /api/jobs HTTP/1.1" 200 OK
[17:12:46] INFO:     127.0.0.1:60943 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:12:46] INFO:     127.0.0.1:60950 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:12:46] INFO:     127.0.0.1:60945 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:13:01] INFO:     127.0.0.1:49407 - "GET /api/departments HTTP/1.1" 200 OK
[17:13:01] INFO:     127.0.0.1:49404 - "GET /api/jobs HTTP/1.1" 200 OK
[17:13:01] INFO:     127.0.0.1:49670 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:13:01] INFO:     127.0.0.1:49403 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:13:01] INFO:     127.0.0.1:49402 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:13:08] E0000 00:00:1794915787.276940   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T11:44:07.170553+00:00
[17:13:08] === Source Location Trace: === 
[17:13:08] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[17:25:24] INFO:     127.0.0.1:54820 - "GET /api/auth/me HTTP/1.1" 200 OK
[17:25:24] INFO:     127.0.0.1:54826 - "GET /api/auth/me HTTP/1.1" 200 OK
[17:25:24] INFO:     127.0.0.1:54828 - "GET /api/auth/me HTTP/1.1" 200 OK
[17:25:24] INFO:     127.0.0.1:54830 - "GET /api/auth/me HTTP/1.1" 200 OK
[17:25:24] INFO:     127.0.0.1:54832 - "GET /api/companies HTTP/1.1" 200 OK
[17:25:24] INFO:     127.0.0.1:55506 - "GET /api/companies HTTP/1.1" 200 OK
[17:25:25] INFO:     127.0.0.1:58890 - "GET /api/settings HTTP/1.1" 200 OK
[17:25:25] INFO:     127.0.0.1:64542 - "GET /api/departments HTTP/1.1" 200 OK
[17:25:25] INFO:     127.0.0.1:64541 - "GET /api/jobs HTTP/1.1" 200 OK
[17:25:25] INFO:     127.0.0.1:55235 - "GET /api/departments HTTP/1.1" 200 OK
[17:25:25] INFO:     127.0.0.1:64538 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[17:25:25] INFO:     127.0.0.1:52137 - "GET /api/settings HTTP/1.1" 200 OK
[17:25:25] INFO:     127.0.0.1:57990 - "GET /api/jobs HTTP/1.1" 200 OK
[17:25:25] INFO:     127.0.0.1:60583 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[17:25:25] INFO:     127.0.0.1:50122 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[17:25:25] INFO:     127.0.0.1:56362 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:50:54] INFO:     127.0.0.1:59420 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:50:54] INFO:     127.0.0.1:64073 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:50:56] INFO:     127.0.0.1:54823 - "GET /api/interview/token/7a73811d-0c2c-46c1-a461-a4125e755041 HTTP/1.1" 200 OK
[20:50:59] INFO:     127.0.0.1:58177 - "GET /api/auth/me HTTP/1.1" 401 Unauthorized
[20:50:59] INFO:     127.0.0.1:58178 - "GET /api/hr/candidates?status=all HTTP/1.1" 401 Unauthorized
[20:50:59] INFO:     127.0.0.1:58179 - "GET /api/hr/dashboard/stats HTTP/1.1" 401 Unauthorized
[20:50:59] INFO:     127.0.0.1:58182 - "GET /api/jobs HTTP/1.1" 401 Unauthorized
[20:50:59] INFO:     127.0.0.1:58183 - "GET /api/departments HTTP/1.1" 401 Unauthorized
[20:50:59] INFO:     127.0.0.1:58337 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 401 Unauthorized
[20:50:59] INFO:     127.0.0.1:60602 - "POST /api/auth/refresh HTTP/1.1" 200 OK
[20:50:59] INFO:     127.0.0.1:64592 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:50:59] INFO:     127.0.0.1:64598 - "GET /api/departments HTTP/1.1" 200 OK
[20:50:59] INFO:     127.0.0.1:64595 - "GET /api/jobs HTTP/1.1" 200 OK
[20:51:00] INFO:     127.0.0.1:64599 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:51:00] INFO:     127.0.0.1:64594 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:51:00] INFO:     127.0.0.1:64593 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:51:00] INFO:     127.0.0.1:56094 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:51:00] INFO:     127.0.0.1:56096 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:51:00] INFO:     127.0.0.1:56098 - "GET /api/companies HTTP/1.1" 200 OK
[20:51:01] INFO:     127.0.0.1:60547 - "GET /api/settings HTTP/1.1" 200 OK
[20:51:01] INFO:     127.0.0.1:52690 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:51:01] INFO:     127.0.0.1:52693 - "GET /api/departments HTTP/1.1" 200 OK
[20:51:01] INFO:     127.0.0.1:52687 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:51:01] INFO:     127.0.0.1:52691 - "GET /api/jobs HTTP/1.1" 200 OK
[20:51:01] INFO:     127.0.0.1:57344 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:51:02] INFO:     127.0.0.1:56093 - "GET /api/interview/token/7a73811d-0c2c-46c1-a461-a4125e755041 HTTP/1.1" 200 OK
[20:51:04] INFO:     127.0.0.1:57993 - "GET /api/interview/token/7a73811d-0c2c-46c1-a461-a4125e755041 HTTP/1.1" 200 OK
[20:51:08] INFO:     127.0.0.1:56473 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:51:08] INFO:     127.0.0.1:51105 - "GET /api/departments HTTP/1.1" 200 OK
[20:51:08] INFO:     127.0.0.1:51104 - "GET /api/jobs HTTP/1.1" 200 OK
[20:51:08] INFO:     127.0.0.1:51106 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:51:08] INFO:     127.0.0.1:51098 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:51:08] INFO:     127.0.0.1:51103 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:51:08] INFO:     127.0.0.1:52483 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:51:08] INFO:     127.0.0.1:52485 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:51:08] INFO:     127.0.0.1:52487 - "GET /api/companies HTTP/1.1" 200 OK
[20:51:10] INFO:     127.0.0.1:49679 - "GET /api/jobs HTTP/1.1" 200 OK
[20:51:10] INFO:     127.0.0.1:49676 - "GET /api/settings HTTP/1.1" 200 OK
[20:51:10] INFO:     127.0.0.1:49680 - "GET /api/departments HTTP/1.1" 200 OK
[20:51:10] INFO:     127.0.0.1:49678 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:51:10] INFO:     127.0.0.1:50564 - "GET /api/jobs HTTP/1.1" 200 OK
[20:51:10] INFO:     127.0.0.1:63207 - "GET /api/departments HTTP/1.1" 200 OK
[20:51:10] INFO:     127.0.0.1:49677 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:51:10] INFO:     127.0.0.1:49682 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:51:10] INFO:     127.0.0.1:59943 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:51:10] INFO:     127.0.0.1:52077 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:51:10] INFO:     127.0.0.1:55837 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:51:10] INFO:     127.0.0.1:64597 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[20:51:10] INFO:     127.0.0.1:59495 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[20:51:10] INFO:     127.0.0.1:64596 - "GET /api/interview/calendar?week_start=2026-11-15 HTTP/1.1" 200 OK
[20:51:10] INFO:     127.0.0.1:53942 - "GET /api/interview/calendar?week_start=2026-11-15 HTTP/1.1" 200 OK
[20:51:23] INFO:     127.0.0.1:53790 - "PATCH /api/settings/interview-availability HTTP/1.1" 422 Unprocessable Entity
[20:51:24] INFO:     127.0.0.1:52237 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:51:24] INFO:     127.0.0.1:52240 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:51:24] INFO:     127.0.0.1:52244 - "GET /api/interview/calendar?week_start=2026-11-15 HTTP/1.1" 200 OK
[20:51:24] INFO:     127.0.0.1:52250 - "GET /api/interview/calendar?week_start=2026-11-15 HTTP/1.1" 200 OK
[20:51:24] INFO:     127.0.0.1:52246 - "GET /api/companies HTTP/1.1" 200 OK
[20:51:24] INFO:     127.0.0.1:52245 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[20:51:24] INFO:     127.0.0.1:62798 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[20:51:25] INFO:     127.0.0.1:64713 - "GET /api/departments HTTP/1.1" 200 OK
[20:51:25] INFO:     127.0.0.1:64712 - "GET /api/jobs HTTP/1.1" 200 OK
[20:51:25] INFO:     127.0.0.1:64707 - "GET /api/settings HTTP/1.1" 200 OK
[20:51:25] INFO:     127.0.0.1:64708 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:51:25] INFO:     127.0.0.1:62783 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:51:25] INFO:     127.0.0.1:64709 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:51:25] INFO:     127.0.0.1:63930 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[20:51:25] INFO:     127.0.0.1:55638 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[20:51:25] INFO:     127.0.0.1:63929 - "GET /api/interview/calendar?week_start=2026-11-15 HTTP/1.1" 200 OK
[20:51:25] INFO:     127.0.0.1:54924 - "GET /api/interview/calendar?week_start=2026-11-15 HTTP/1.1" 200 OK
[20:51:40] INFO:     127.0.0.1:56139 - "GET /api/departments HTTP/1.1" 200 OK
[20:51:40] INFO:     127.0.0.1:56137 - "GET /api/jobs HTTP/1.1" 200 OK
[20:51:40] INFO:     127.0.0.1:56141 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:51:40] INFO:     127.0.0.1:56138 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:51:40] INFO:     127.0.0.1:56136 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:51:40] INFO:     127.0.0.1:58051 - "GET /api/interview/calendar?week_start=2026-11-15 HTTP/1.1" 200 OK
[20:51:42] INFO:     127.0.0.1:51594 - "PATCH /api/settings/interview-availability HTTP/1.1" 422 Unprocessable Entity
[20:51:47] INFO:     127.0.0.1:57675 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:51:47] INFO:     127.0.0.1:57678 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:51:47] INFO:     127.0.0.1:57682 - "GET /api/interview/calendar?week_start=2026-11-15 HTTP/1.1" 200 OK
[20:51:47] INFO:     127.0.0.1:57688 - "GET /api/interview/calendar?week_start=2026-11-15 HTTP/1.1" 200 OK
[20:51:47] INFO:     127.0.0.1:57683 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[20:51:47] INFO:     127.0.0.1:57684 - "GET /api/companies HTTP/1.1" 200 OK
[20:51:47] INFO:     127.0.0.1:64548 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[20:51:47] INFO:     127.0.0.1:49673 - "GET /api/settings HTTP/1.1" 200 OK
[20:51:47] INFO:     127.0.0.1:49686 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:51:47] INFO:     127.0.0.1:49688 - "GET /api/departments HTTP/1.1" 200 OK
[20:51:47] INFO:     127.0.0.1:49687 - "GET /api/jobs HTTP/1.1" 200 OK
[20:51:48] INFO:     127.0.0.1:49674 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:51:48] INFO:     127.0.0.1:49689 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:51:48] INFO:     127.0.0.1:56591 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[20:51:48] INFO:     127.0.0.1:56590 - "GET /api/interview/calendar?week_start=2026-11-15 HTTP/1.1" 200 OK
[20:51:48] INFO:     127.0.0.1:50522 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[20:51:48] INFO:     127.0.0.1:55603 - "GET /api/interview/calendar?week_start=2026-11-15 HTTP/1.1" 200 OK
[20:52:02] INFO:     127.0.0.1:56162 - "GET /api/departments HTTP/1.1" 200 OK
[20:52:02] INFO:     127.0.0.1:56165 - "GET /api/jobs HTTP/1.1" 200 OK
[20:52:02] INFO:     127.0.0.1:56166 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:52:02] INFO:     127.0.0.1:56159 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:52:02] INFO:     127.0.0.1:56157 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:52:02] INFO:     127.0.0.1:60852 - "GET /api/interview/calendar?week_start=2026-11-15 HTTP/1.1" 200 OK
[20:52:10] INFO:     127.0.0.1:65523 - "PATCH /api/settings/interview-availability HTTP/1.1" 200 OK
[20:52:17] INFO:     127.0.0.1:59971 - "GET /api/departments HTTP/1.1" 200 OK
[20:52:17] INFO:     127.0.0.1:59970 - "GET /api/jobs HTTP/1.1" 200 OK
[20:52:17] INFO:     127.0.0.1:59972 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:52:17] INFO:     127.0.0.1:59967 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:52:17] INFO:     127.0.0.1:59966 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:52:17] INFO:     127.0.0.1:55090 - "GET /api/interview/calendar?week_start=2026-11-15 HTTP/1.1" 200 OK
[20:52:31] INFO:     127.0.0.1:62655 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:52:31] INFO:     127.0.0.1:51133 - "GET /api/departments HTTP/1.1" 200 OK
[20:52:31] INFO:     127.0.0.1:51132 - "GET /api/jobs HTTP/1.1" 200 OK
[20:52:31] INFO:     127.0.0.1:51136 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:52:31] INFO:     127.0.0.1:51134 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:52:31] INFO:     127.0.0.1:51131 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:52:34] INFO:     127.0.0.1:55838 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:52:35] INFO:     127.0.0.1:55843 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:52:35] INFO:     127.0.0.1:55845 - "GET /api/companies HTTP/1.1" 200 OK
[20:52:35] INFO:     127.0.0.1:54042 - "GET /api/departments HTTP/1.1" 200 OK
[20:52:35] INFO:     127.0.0.1:54041 - "GET /api/jobs HTTP/1.1" 200 OK
[20:52:35] INFO:     127.0.0.1:54037 - "GET /api/settings HTTP/1.1" 200 OK
[20:52:35] INFO:     127.0.0.1:54038 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:52:35] INFO:     127.0.0.1:54039 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:52:35] INFO:     127.0.0.1:54902 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:52:37] INFO:     127.0.0.1:55837 - "GET /api/interview/token/7a73811d-0c2c-46c1-a461-a4125e755041 HTTP/1.1" 200 OK
[20:52:41] INFO:     127.0.0.1:50339 - "GET /api/interview/token/7a73811d-0c2c-46c1-a461-a4125e755041 HTTP/1.1" 200 OK
[20:52:47] 2026-11-17 20:52:46,106 | ERROR | services.email_service | SMTP send failed for to=ravi.molake@rrglobal.com
[20:52:47] Traceback (most recent call last):
[20:52:47]   File "C:\Users\ravi.molake\Downloads\Interview_Agentic_AI\backend\services\email_service.py", line 139, in _send_message
[20:52:47]     with smtplib.SMTP(
[20:52:47]          ^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\AppData\Local\Programs\Python\Python311\Lib\smtplib.py", line 255, in __init__
[20:52:47]     (code, msg) = self.connect(host, port)
[20:52:47]                   ^^^^^^^^^^^^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\AppData\Local\Programs\Python\Python311\Lib\smtplib.py", line 341, in connect
[20:52:47]     self.sock = self._get_socket(host, port, self.timeout)
[20:52:47]                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\AppData\Local\Programs\Python\Python311\Lib\smtplib.py", line 312, in _get_socket
[20:52:47]     return socket.create_connection((host, port), timeout,
[20:52:47]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\AppData\Local\Programs\Python\Python311\Lib\socket.py", line 826, in create_connection
[20:52:47]     for res in getaddrinfo(host, port, 0, SOCK_STREAM):
[20:52:47]                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\AppData\Local\Programs\Python\Python311\Lib\socket.py", line 961, in getaddrinfo
[20:52:47]     for res in _socket.getaddrinfo(host, port, family, type, proto, flags):
[20:52:47]                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[20:52:47] socket.gaierror: [Errno 11001] getaddrinfo failed
[20:52:47] 2026-11-17 20:52:46,188 | ERROR | agents.scheduler_agent.graph | LangGraph slot resume failed for CAND-26907EAD; booking from database
[20:52:47] Traceback (most recent call last):
[20:52:47]   File "C:\Users\ravi.molake\Downloads\Interview_Agentic_AI\backend\services\email_service.py", line 139, in _send_message
[20:52:47]     with smtplib.SMTP(
[20:52:47]          ^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\AppData\Local\Programs\Python\Python311\Lib\smtplib.py", line 255, in __init__
[20:52:47]     (code, msg) = self.connect(host, port)
[20:52:47]                   ^^^^^^^^^^^^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\AppData\Local\Programs\Python\Python311\Lib\smtplib.py", line 341, in connect
[20:52:47]     self.sock = self._get_socket(host, port, self.timeout)
[20:52:47]                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\AppData\Local\Programs\Python\Python311\Lib\smtplib.py", line 312, in _get_socket
[20:52:47]     return socket.create_connection((host, port), timeout,
[20:52:47]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\AppData\Local\Programs\Python\Python311\Lib\socket.py", line 826, in create_connection
[20:52:47]     for res in getaddrinfo(host, port, 0, SOCK_STREAM):
[20:52:47]                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\AppData\Local\Programs\Python\Python311\Lib\socket.py", line 961, in getaddrinfo
[20:52:47]     for res in _socket.getaddrinfo(host, port, family, type, proto, flags):
[20:52:47]                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[20:52:47] socket.gaierror: [Errno 11001] getaddrinfo failed
[20:52:47] 
[20:52:47] The above exception was the direct cause of the following exception:
[20:52:47] 
[20:52:47] Traceback (most recent call last):
[20:52:47]   File "C:\Users\ravi.molake\Downloads\Interview_Agentic_AI\backend\agents\scheduler_agent\graph.py", line 194, in resume_with_slot
[20:52:47]     result = await ainvoke_graph(
[20:52:47]              ^^^^^^^^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\Downloads\Interview_Agentic_AI\backend\core\langgraph_runtime.py", line 122, in ainvoke_graph
[20:52:47]     return await graph.ainvoke(input_state, config=config)
[20:52:47]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\Downloads\Interview_Agentic_AI\backend\venv\Lib\site-packages\langgraph\pregel\__init__.py", line 1989, in ainvoke
[20:52:47]     async for chunk in self.astream(
[20:52:47]   File "C:\Users\ravi.molake\AppData\Local\Programs\Python\Python311\Lib\contextlib.py", line 222, in __aexit__
[20:52:47]     await self.gen.athrow(typ, value, traceback)
[20:52:47]   File "C:\Users\ravi.molake\Downloads\Interview_Agentic_AI\backend\venv\Lib\site-packages\langgraph\pregel\manager.py", line 90, in AsyncChannelsManager
[20:52:47]     yield (
[20:52:47]   File "C:\Users\ravi.molake\Downloads\Interview_Agentic_AI\backend\venv\Lib\site-packages\langgraph\pregel\__init__.py", line 1874, in astream
[20:52:47]     async for _ in runner.atick(
[20:52:47]   File "C:\Users\ravi.molake\Downloads\Interview_Agentic_AI\backend\venv\Lib\site-packages\langgraph\pregel\runner.py", line 362, in atick
[20:52:47]     await arun_with_retry(
[20:52:47]   File "C:\Users\ravi.molake\Downloads\Interview_Agentic_AI\backend\venv\Lib\site-packages\langgraph\pregel\retry.py", line 132, in arun_with_retry
[20:52:47]     return await task.proc.ainvoke(task.input, config)
[20:52:47]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\Downloads\Interview_Agentic_AI\backend\venv\Lib\site-packages\langgraph\utils\runnable.py", line 445, in ainvoke
[20:52:47]     input = await step.ainvoke(input, config, **kwargs)
[20:52:47]             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\Downloads\Interview_Agentic_AI\backend\venv\Lib\site-packages\langgraph\utils\runnable.py", line 236, in ainvoke
[20:52:47]     ret = await asyncio.create_task(coro, context=context)
[20:52:47]           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\Downloads\Interview_Agentic_AI\backend\agents\scheduler_agent\nodes.py", line 293, in send_confirmation_email
[20:52:47]     self.email_service.send_confirmation_email(
[20:52:47]   File "C:\Users\ravi.molake\Downloads\Interview_Agentic_AI\backend\services\email_service.py", line 218, in send_confirmation_email
[20:52:47]     return self._send_message(
[20:52:47]            ^^^^^^^^^^^^^^^^^^^
[20:52:47]   File "C:\Users\ravi.molake\Downloads\Interview_Agentic_AI\backend\services\email_service.py", line 156, in _send_message
[20:52:47]     raise RuntimeError(f"Failed to send email: {exc}") from exc
[20:52:47] RuntimeError: Failed to send email: [Errno 11001] getaddrinfo failed
[20:52:47] During task with name 'send_confirmation_email' and id '042b0dfd-fd15-0806-d5e1-24ea4ccfa06a'
[20:52:47] INFO:     127.0.0.1:65421 - "POST /api/interview/book-slot HTTP/1.1" 409 Conflict
[20:52:51] INFO:     127.0.0.1:63669 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:52:51] INFO:     127.0.0.1:63668 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:52:51] INFO:     127.0.0.1:63673 - "GET /api/departments HTTP/1.1" 200 OK
[20:52:51] INFO:     127.0.0.1:63675 - "GET /api/jobs HTTP/1.1" 200 OK
[20:52:51] INFO:     127.0.0.1:63674 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:53:03] 2026-11-17 20:53:02,559 | INFO | services.email_service | Email sent via SMTP to=ravi.molake@rrglobal.com subject=RR Kabel | Interview Scheduled Successfully
[20:53:03] INFO:     127.0.0.1:60503 - "GET /api/departments HTTP/1.1" 200 OK
[20:53:03] INFO:     127.0.0.1:60500 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:53:03] INFO:     127.0.0.1:60501 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:53:03] 2026-11-17 20:53:03,163 | INFO | services.blueprint_service | Skipping Agent 3/4 for CAND-26907EAD until interview is scheduled (status=CandidateStatus.SHORTLISTED)
[20:53:03] INFO:     127.0.0.1:60499 - "POST /api/interview/book-slot HTTP/1.1" 200 OK
[20:53:03] INFO:     127.0.0.1:60504 - "GET /api/jobs HTTP/1.1" 200 OK
[20:53:03] INFO:     127.0.0.1:50298 - "GET /api/departments HTTP/1.1" 200 OK
[20:53:03] INFO:     127.0.0.1:59432 - "GET /api/jobs HTTP/1.1" 200 OK
[20:53:03] INFO:     127.0.0.1:65103 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:53:03] INFO:     127.0.0.1:60505 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:53:03] INFO:     127.0.0.1:53124 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:53:04] INFO:     127.0.0.1:62134 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:53:07] INFO:     127.0.0.1:60692 - "GET /api/departments HTTP/1.1" 200 OK
[20:53:07] INFO:     127.0.0.1:60695 - "GET /api/jobs HTTP/1.1" 200 OK
[20:53:07] INFO:     127.0.0.1:60693 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:53:07] INFO:     127.0.0.1:60696 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:53:07] INFO:     127.0.0.1:60694 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:53:29] INFO:     127.0.0.1:50559 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:53:29] INFO:     127.0.0.1:50557 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:53:29] INFO:     127.0.0.1:50564 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:53:29] INFO:     127.0.0.1:50565 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:53:29] INFO:     127.0.0.1:50568 - "GET /api/companies HTTP/1.1" 200 OK
[20:53:29] INFO:     127.0.0.1:65143 - "GET /api/settings HTTP/1.1" 200 OK
[20:53:29] INFO:     127.0.0.1:65149 - "GET /api/departments HTTP/1.1" 200 OK
[20:53:29] INFO:     127.0.0.1:65151 - "GET /api/jobs HTTP/1.1" 200 OK
[20:53:29] INFO:     127.0.0.1:65144 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:53:29] INFO:     127.0.0.1:65152 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:53:29] INFO:     127.0.0.1:65150 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:53:33] INFO:     127.0.0.1:53402 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:53:33] INFO:     127.0.0.1:53409 - "GET /api/departments HTTP/1.1" 200 OK
[20:53:33] INFO:     127.0.0.1:53408 - "GET /api/jobs HTTP/1.1" 200 OK
[20:53:33] INFO:     127.0.0.1:53410 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:53:33] INFO:     127.0.0.1:53406 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:53:33] INFO:     127.0.0.1:53407 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:53:37] INFO:     127.0.0.1:64240 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:53:37] INFO:     127.0.0.1:53469 - "GET /api/departments HTTP/1.1" 200 OK
[20:53:37] INFO:     127.0.0.1:53467 - "GET /api/jobs HTTP/1.1" 200 OK
[20:53:37] INFO:     127.0.0.1:53242 - "GET /api/interview/calendar?week_start=2026-11-15 HTTP/1.1" 200 OK
[20:53:38] INFO:     127.0.0.1:53470 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:53:38] INFO:     127.0.0.1:53465 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:53:38] INFO:     127.0.0.1:53466 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:53:42] INFO:     127.0.0.1:53338 - "GET /api/departments HTTP/1.1" 200 OK
[20:53:42] INFO:     127.0.0.1:53337 - "GET /api/jobs HTTP/1.1" 200 OK
[20:53:42] INFO:     127.0.0.1:53339 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:53:42] INFO:     127.0.0.1:53336 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:53:42] INFO:     127.0.0.1:53335 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:53:49] INFO:     127.0.0.1:58972 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:53:49] INFO:     127.0.0.1:58980 - "GET /api/departments HTTP/1.1" 200 OK
[20:53:49] INFO:     127.0.0.1:58979 - "GET /api/jobs HTTP/1.1" 200 OK
[20:53:50] INFO:     127.0.0.1:58983 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:53:50] INFO:     127.0.0.1:58978 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:53:50] INFO:     127.0.0.1:58977 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:54:36] INFO:     127.0.0.1:55140 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:54:36] INFO:     127.0.0.1:55141 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:54:36] INFO:     127.0.0.1:55145 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:54:36] INFO:     127.0.0.1:55147 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:54:36] INFO:     127.0.0.1:55149 - "GET /api/companies HTTP/1.1" 200 OK
[20:54:37] INFO:     127.0.0.1:62575 - "GET /api/settings HTTP/1.1" 200 OK
[20:54:37] INFO:     127.0.0.1:61867 - "GET /api/departments HTTP/1.1" 200 OK
[20:54:37] INFO:     127.0.0.1:61863 - "GET /api/jobs HTTP/1.1" 200 OK
[20:54:37] INFO:     127.0.0.1:61866 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:54:37] INFO:     127.0.0.1:61862 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:54:37] INFO:     127.0.0.1:61861 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:54:43] INFO:     127.0.0.1:54021 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:54:43] INFO:     127.0.0.1:54031 - "GET /api/departments HTTP/1.1" 200 OK
[20:54:43] INFO:     127.0.0.1:54030 - "GET /api/jobs HTTP/1.1" 200 OK
[20:54:43] INFO:     127.0.0.1:54032 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:54:43] INFO:     127.0.0.1:54029 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:54:43] INFO:     127.0.0.1:54028 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:54:44] INFO:     127.0.0.1:55255 - "GET /api/hr/candidates/CAND-26907EAD HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:51446 - "GET /api/hr/candidates/CAND-26907EAD HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:49678 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:49676 - "GET /api/interview/blueprint/candidates/CAND-26907EAD HTTP/1.1" 404 Not Found
[20:54:46] INFO:     127.0.0.1:49680 - "GET /api/interview/agent6/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:49681 - "GET /api/interview/agent6/candidates/CAND-26907EAD/evaluations HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:49679 - "GET /api/interview/agent4/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:58471 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:49395 - "GET /api/interview/agent5/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:54112 - "GET /api/interview/room/candidates/CAND-26907EAD/runtime HTTP/1.1" 409 Conflict
[20:54:46] INFO:     127.0.0.1:60830 - "GET /api/interview/blueprint/candidates/CAND-26907EAD HTTP/1.1" 404 Not Found
[20:54:46] INFO:     127.0.0.1:60205 - "POST /api/interview/blueprint/candidates/CAND-26907EAD HTTP/1.1" 409 Conflict
[20:54:46] INFO:     127.0.0.1:58870 - "GET /api/interview/agent7/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:54299 - "GET /api/interview/agent6/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:51266 - "GET /api/hr/candidates/CAND-26907EAD HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:56908 - "GET /api/interview/agent6/candidates/CAND-26907EAD/evaluations HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:65114 - "GET /api/interview/agent4/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:54798 - "GET /api/interview/agent5/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:54464 - "GET /api/interview/agent7/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:56254 - "GET /api/interview/room/candidates/CAND-26907EAD/runtime HTTP/1.1" 409 Conflict
[20:54:46] INFO:     127.0.0.1:55970 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:57800 - "GET /api/hr/candidates/CAND-26907EAD HTTP/1.1" 200 OK
[20:54:46] INFO:     127.0.0.1:64631 - "GET /api/interview/blueprint/candidates/CAND-26907EAD HTTP/1.1" 404 Not Found
[20:54:46] INFO:     127.0.0.1:60045 - "GET /api/interview/agent6/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:47] INFO:     127.0.0.1:57421 - "GET /api/interview/agent5/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:47] INFO:     127.0.0.1:64202 - "GET /api/interview/agent6/candidates/CAND-26907EAD/evaluations HTTP/1.1" 200 OK
[20:54:47] INFO:     127.0.0.1:60072 - "GET /api/interview/room/candidates/CAND-26907EAD/runtime HTTP/1.1" 409 Conflict
[20:54:47] INFO:     127.0.0.1:64203 - "GET /api/interview/agent4/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:47] INFO:     127.0.0.1:59700 - "GET /api/interview/agent7/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:47] INFO:     127.0.0.1:64207 - "GET /api/interview/blueprint/candidates/CAND-26907EAD HTTP/1.1" 404 Not Found
[20:54:47] INFO:     127.0.0.1:51181 - "GET /api/settings/interview-availability HTTP/1.1" 200 OK
[20:54:47] INFO:     127.0.0.1:51183 - "POST /api/interview/blueprint/candidates/CAND-26907EAD HTTP/1.1" 409 Conflict
[20:54:47] INFO:     127.0.0.1:62243 - "GET /api/interview/agent5/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:47] INFO:     127.0.0.1:58502 - "GET /api/interview/agent6/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:47] INFO:     127.0.0.1:63667 - "GET /api/interview/room/candidates/CAND-26907EAD/runtime HTTP/1.1" 409 Conflict
[20:54:47] INFO:     127.0.0.1:55787 - "GET /api/interview/agent6/candidates/CAND-26907EAD/evaluations HTTP/1.1" 200 OK
[20:54:47] INFO:     127.0.0.1:53293 - "GET /api/interview/agent4/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:47] INFO:     127.0.0.1:51984 - "GET /api/departments HTTP/1.1" 200 OK
[20:54:47] INFO:     127.0.0.1:50858 - "GET /api/interview/agent7/candidates/CAND-26907EAD/status HTTP/1.1" 200 OK
[20:54:47] INFO:     127.0.0.1:51983 - "GET /api/jobs HTTP/1.1" 200 OK
[20:54:48] INFO:     127.0.0.1:51981 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:54:48] INFO:     127.0.0.1:64689 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:54:48] INFO:     127.0.0.1:58185 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:54:52] INFO:     127.0.0.1:50504 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:54:52] INFO:     127.0.0.1:50507 - "GET /api/departments HTTP/1.1" 200 OK
[20:54:52] INFO:     127.0.0.1:50503 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:54:52] INFO:     127.0.0.1:50505 - "GET /api/jobs HTTP/1.1" 200 OK
[20:54:52] INFO:     127.0.0.1:50508 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:54:52] INFO:     127.0.0.1:50509 - "GET /api/hr/candidates/CAND-26907EAD HTTP/1.1" 200 OK
[20:54:52] INFO:     127.0.0.1:60234 - "GET /api/interview/room/candidates/CAND-26907EAD/runtime HTTP/1.1" 409 Conflict
[20:55:05] INFO:     127.0.0.1:51313 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:05] INFO:     127.0.0.1:51315 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:05] INFO:     127.0.0.1:51319 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:05] INFO:     127.0.0.1:51321 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:05] INFO:     127.0.0.1:51323 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:06] INFO:     127.0.0.1:62316 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:06] INFO:     127.0.0.1:62776 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:06] INFO:     127.0.0.1:62771 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:06] INFO:     127.0.0.1:62773 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:06] INFO:     127.0.0.1:62777 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:06] INFO:     127.0.0.1:62772 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:08] INFO:     127.0.0.1:63486 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:08] INFO:     127.0.0.1:63485 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:08] INFO:     127.0.0.1:63488 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:08] INFO:     127.0.0.1:63490 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:08] INFO:     127.0.0.1:63492 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:09] INFO:     127.0.0.1:58127 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:09] INFO:     127.0.0.1:58132 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:09] INFO:     127.0.0.1:58130 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:09] INFO:     127.0.0.1:58128 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:09] INFO:     127.0.0.1:58133 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:09] INFO:     127.0.0.1:58129 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:09] INFO:     127.0.0.1:60983 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:09] INFO:     127.0.0.1:60984 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:09] INFO:     127.0.0.1:60988 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:09] INFO:     127.0.0.1:60986 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:09] INFO:     127.0.0.1:60990 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:09] INFO:     127.0.0.1:63891 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:09] INFO:     127.0.0.1:63892 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:09] INFO:     127.0.0.1:63884 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:09] INFO:     127.0.0.1:63889 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:09] INFO:     127.0.0.1:63885 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:10] INFO:     127.0.0.1:63886 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:10] INFO:     127.0.0.1:61189 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:10] INFO:     127.0.0.1:61188 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:10] INFO:     127.0.0.1:61191 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:10] INFO:     127.0.0.1:61195 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:10] INFO:     127.0.0.1:61193 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:10] INFO:     127.0.0.1:52030 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:10] INFO:     127.0.0.1:52029 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:10] INFO:     127.0.0.1:52032 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:10] INFO:     127.0.0.1:52034 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:10] INFO:     127.0.0.1:52036 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:10] INFO:     127.0.0.1:64414 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:63001 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:62994 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:63000 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:49673 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:11] INFO:     127.0.0.1:49675 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:63002 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:62999 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:49683 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:11] INFO:     127.0.0.1:49685 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:49687 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:51110 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:51106 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:51111 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:51105 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:51112 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:56795 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:56794 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:11] INFO:     127.0.0.1:51103 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:56799 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:11] INFO:     127.0.0.1:56798 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:64447 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:64450 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:64448 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:11] INFO:     127.0.0.1:64452 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:11] INFO:     127.0.0.1:64454 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:54117 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:54116 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:54115 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:54113 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:54119 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:54114 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:54261 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:11] INFO:     127.0.0.1:54262 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:54264 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:11] INFO:     127.0.0.1:54266 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:57691 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:11] INFO:     127.0.0.1:57692 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:57694 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:11] INFO:     127.0.0.1:57696 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:11] INFO:     127.0.0.1:57698 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:53835 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:53836 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:50472 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:53834 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:53828 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:53833 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:64694 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:64692 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:12] INFO:     127.0.0.1:64696 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:64698 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:12] INFO:     127.0.0.1:64700 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:53218 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:53219 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:53213 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:53215 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:56036 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:56035 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:12] INFO:     127.0.0.1:53214 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:56038 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:53216 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:55119 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:12] INFO:     127.0.0.1:55121 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:55124 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:12] INFO:     127.0.0.1:55125 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:55127 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:61659 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:61658 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:61651 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:61657 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:61652 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:61656 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:56142 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:56141 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:12] INFO:     127.0.0.1:56145 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:12] INFO:     127.0.0.1:56146 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:12] INFO:     127.0.0.1:56148 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:58844 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:58843 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:58841 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:58837 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:58842 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:58838 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:53723 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:13] INFO:     127.0.0.1:53724 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:53728 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:53727 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:13] INFO:     127.0.0.1:53730 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:62976 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:62975 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:62972 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:62973 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:63903 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:13] INFO:     127.0.0.1:63904 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:62974 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:62978 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:63908 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:63907 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:13] INFO:     127.0.0.1:64003 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:13] INFO:     127.0.0.1:64004 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:64007 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:13] INFO:     127.0.0.1:64008 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:64010 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:59882 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:59880 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:59876 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:65531 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:13] INFO:     127.0.0.1:65533 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:59874 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:59881 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:59875 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:13] INFO:     127.0.0.1:60402 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:14] INFO:     127.0.0.1:59162 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:14] INFO:     127.0.0.1:59164 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:59166 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:14] INFO:     127.0.0.1:59168 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:59170 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:50137 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:50135 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:50134 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:50130 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:50138 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:50133 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:59883 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:14] INFO:     127.0.0.1:59884 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:59887 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:14] INFO:     127.0.0.1:59888 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:59890 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:63107 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:14] INFO:     127.0.0.1:63108 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:63110 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:14] INFO:     127.0.0.1:63112 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:63114 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:56131 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:56130 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:56128 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:56132 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:56129 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:56125 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:59920 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:59919 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:14] INFO:     127.0.0.1:59922 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:14] INFO:     127.0.0.1:59924 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:14] INFO:     127.0.0.1:59926 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:52850 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:52849 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:52843 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:52847 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:52848 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:57672 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:15] INFO:     127.0.0.1:57674 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:52851 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:57676 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:15] INFO:     127.0.0.1:57678 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:57680 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:60352 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:60351 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:60342 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:60350 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:56383 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:15] INFO:     127.0.0.1:56384 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:60348 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:56386 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:15] INFO:     127.0.0.1:56388 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:60347 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:56390 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:56802 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:56798 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:56797 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:56792 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:56801 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:56793 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:60952 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:15] INFO:     127.0.0.1:60954 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:60956 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:15] INFO:     127.0.0.1:60958 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:15] INFO:     127.0.0.1:60960 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:55673 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:55665 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:55672 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:55671 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:55674 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:55666 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:62913 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:62911 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:16] INFO:     127.0.0.1:62915 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:62917 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:16] INFO:     127.0.0.1:62919 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:53930 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:53933 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:53924 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:53931 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:53932 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:53925 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:59480 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:16] INFO:     127.0.0.1:59481 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:59483 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:16] INFO:     127.0.0.1:59485 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:59487 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:50978 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:50980 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:50975 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:55439 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:16] INFO:     127.0.0.1:55440 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:50977 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:50982 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:55443 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:16] INFO:     127.0.0.1:55444 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:50976 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:59905 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:16] INFO:     127.0.0.1:59906 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:59909 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:16] INFO:     127.0.0.1:59910 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:50017 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:16] INFO:     127.0.0.1:50018 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:50020 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:16] INFO:     127.0.0.1:50022 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:16] INFO:     127.0.0.1:50024 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:17] INFO:     127.0.0.1:53647 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:17] INFO:     127.0.0.1:53645 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:17] INFO:     127.0.0.1:53643 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:17] INFO:     127.0.0.1:53644 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:17] INFO:     127.0.0.1:53648 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:17] INFO:     127.0.0.1:53649 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:62527 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:62526 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:27] INFO:     127.0.0.1:61023 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:61022 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:27] INFO:     127.0.0.1:54321 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:27] INFO:     127.0.0.1:54322 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:54324 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:27] INFO:     127.0.0.1:54326 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:54328 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:64513 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:64510 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:64514 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:64512 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:64895 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:27] INFO:     127.0.0.1:64897 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:64511 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:64901 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:64899 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:27] INFO:     127.0.0.1:64903 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:64516 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:60761 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:60762 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:60753 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:60759 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:60763 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:60758 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:65048 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:27] INFO:     127.0.0.1:65049 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:65053 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:27] INFO:     127.0.0.1:65052 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:27] INFO:     127.0.0.1:65055 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:49692 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:49691 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:49677 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:49690 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:49689 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:49688 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:65447 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:65446 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:29] INFO:     127.0.0.1:65449 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:65451 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:29] INFO:     127.0.0.1:65453 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:53462 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:29] INFO:     127.0.0.1:53463 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:53465 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:29] INFO:     127.0.0.1:53468 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:53471 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:53460 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:53457 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:53451 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:53458 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:57630 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:29] INFO:     127.0.0.1:57633 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:53456 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:57635 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:29] INFO:     127.0.0.1:57637 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:53455 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:53493 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:29] INFO:     127.0.0.1:53494 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:53496 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:29] INFO:     127.0.0.1:53498 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:53500 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:62556 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:62553 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:62549 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:62554 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:62552 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:51385 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:51384 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:29] INFO:     127.0.0.1:51388 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:29] INFO:     127.0.0.1:62551 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:30] INFO:     127.0.0.1:53354 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:30] INFO:     127.0.0.1:53355 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:30] INFO:     127.0.0.1:53357 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:30] INFO:     127.0.0.1:51389 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:30] INFO:     127.0.0.1:53360 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:30] INFO:     127.0.0.1:53362 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:30] INFO:     127.0.0.1:65159 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:30] INFO:     127.0.0.1:65157 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:30] INFO:     127.0.0.1:65158 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:30] INFO:     127.0.0.1:65162 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:30] INFO:     127.0.0.1:65161 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:30] INFO:     127.0.0.1:65163 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:30] INFO:     127.0.0.1:53907 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:30] INFO:     127.0.0.1:53905 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:30] INFO:     127.0.0.1:53909 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:30] INFO:     127.0.0.1:53911 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:30] INFO:     127.0.0.1:53913 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:65128 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:65123 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:65127 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:65129 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:65126 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:55542 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:55541 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:31] INFO:     127.0.0.1:65130 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:56950 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:56949 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:31] INFO:     127.0.0.1:56952 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:56954 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:31] INFO:     127.0.0.1:56956 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:58759 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:58753 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:58760 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:58755 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:49907 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:31] INFO:     127.0.0.1:49909 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:58754 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:49912 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:31] INFO:     127.0.0.1:58761 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:49684 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:49677 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:31] INFO:     127.0.0.1:49687 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:49688 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:31] INFO:     127.0.0.1:49691 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:50554 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:50552 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:50547 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:50546 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:31] INFO:     127.0.0.1:50548 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:32] INFO:     127.0.0.1:63644 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:32] INFO:     127.0.0.1:63645 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:32] INFO:     127.0.0.1:50553 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:32] INFO:     127.0.0.1:63648 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:32] INFO:     127.0.0.1:63649 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:32] INFO:     127.0.0.1:63651 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:32] INFO:     127.0.0.1:59215 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:32] INFO:     127.0.0.1:59216 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:32] INFO:     127.0.0.1:51004 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:32] INFO:     127.0.0.1:51005 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:32] INFO:     127.0.0.1:51007 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:32] INFO:     127.0.0.1:51009 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:32] INFO:     127.0.0.1:59221 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:32] INFO:     127.0.0.1:59222 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:32] INFO:     127.0.0.1:51011 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:32] INFO:     127.0.0.1:52679 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:32] INFO:     127.0.0.1:52676 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:32] INFO:     127.0.0.1:52682 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:32] INFO:     127.0.0.1:52678 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:32] INFO:     127.0.0.1:52677 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:32] INFO:     127.0.0.1:52681 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:57935 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:57937 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:57934 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:33] INFO:     127.0.0.1:57939 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:57941 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:33] INFO:     127.0.0.1:49798 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:64936 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:33] INFO:     127.0.0.1:64937 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:49797 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:49795 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:51189 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:33] INFO:     127.0.0.1:51190 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:49801 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:51193 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:33] INFO:     127.0.0.1:51195 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:49796 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:51197 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:49802 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:54585 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:33] INFO:     127.0.0.1:54586 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:54588 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:33] INFO:     127.0.0.1:54590 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:33] INFO:     127.0.0.1:54592 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:34] INFO:     127.0.0.1:53008 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:34] INFO:     127.0.0.1:53007 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:34] INFO:     127.0.0.1:52999 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:34] INFO:     127.0.0.1:60306 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:34] INFO:     127.0.0.1:60305 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:34] INFO:     127.0.0.1:53009 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:34] INFO:     127.0.0.1:53006 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:34] INFO:     127.0.0.1:60308 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:34] INFO:     127.0.0.1:53000 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:34] INFO:     127.0.0.1:60310 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:34] INFO:     127.0.0.1:60312 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:34] INFO:     127.0.0.1:52337 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:34] INFO:     127.0.0.1:52340 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:34] INFO:     127.0.0.1:53925 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:34] INFO:     127.0.0.1:53371 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:35] INFO:     127.0.0.1:52336 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:35] INFO:     127.0.0.1:53370 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:35] INFO:     127.0.0.1:53373 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:35] INFO:     127.0.0.1:54875 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:35] INFO:     127.0.0.1:52341 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:35] INFO:     127.0.0.1:54876 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:35] INFO:     127.0.0.1:64720 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:35] INFO:     127.0.0.1:51233 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:35] INFO:     127.0.0.1:51235 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:35] INFO:     127.0.0.1:51232 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:35] INFO:     127.0.0.1:53382 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:35] INFO:     127.0.0.1:53383 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:35] INFO:     127.0.0.1:53391 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:35] INFO:     127.0.0.1:53393 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:35] INFO:     127.0.0.1:63653 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:35] INFO:     127.0.0.1:63654 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:35] INFO:     127.0.0.1:53395 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:35] INFO:     127.0.0.1:50942 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:35] INFO:     127.0.0.1:50941 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:35] INFO:     127.0.0.1:50933 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:35] INFO:     127.0.0.1:50943 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:35] INFO:     127.0.0.1:50940 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:36] INFO:     127.0.0.1:50939 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:36] INFO:     127.0.0.1:52656 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:36] INFO:     127.0.0.1:52657 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:36] INFO:     127.0.0.1:59404 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:36] INFO:     127.0.0.1:59405 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:36] INFO:     127.0.0.1:59407 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:36] INFO:     127.0.0.1:59409 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:36] INFO:     127.0.0.1:59411 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:37] INFO:     127.0.0.1:64032 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:37] INFO:     127.0.0.1:64033 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:37] INFO:     127.0.0.1:64037 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:37] INFO:     127.0.0.1:64036 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:37] INFO:     127.0.0.1:52893 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:37] INFO:     127.0.0.1:52892 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:37] INFO:     127.0.0.1:64038 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:37] INFO:     127.0.0.1:52895 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:37] INFO:     127.0.0.1:64035 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:37] INFO:     127.0.0.1:52897 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:37] INFO:     127.0.0.1:52899 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:37] INFO:     127.0.0.1:57161 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:37] INFO:     127.0.0.1:57159 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:37] INFO:     127.0.0.1:57158 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:37] INFO:     127.0.0.1:57160 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:37] INFO:     127.0.0.1:57162 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:37] INFO:     127.0.0.1:57152 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:38] INFO:     127.0.0.1:56136 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:38] INFO:     127.0.0.1:56137 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:38] INFO:     127.0.0.1:56139 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:38] INFO:     127.0.0.1:56143 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:38] INFO:     127.0.0.1:56146 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:38] INFO:     127.0.0.1:57222 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:38] INFO:     127.0.0.1:57221 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:38] INFO:     127.0.0.1:57215 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:38] INFO:     127.0.0.1:57223 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:38] INFO:     127.0.0.1:57072 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:39] INFO:     127.0.0.1:57220 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:39] INFO:     127.0.0.1:57071 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:39] INFO:     127.0.0.1:57074 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:39] INFO:     127.0.0.1:57224 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:39] INFO:     127.0.0.1:51322 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:39] INFO:     127.0.0.1:51324 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:39] INFO:     127.0.0.1:51327 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:39] INFO:     127.0.0.1:51328 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:39] INFO:     127.0.0.1:51330 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:39] INFO:     127.0.0.1:56923 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:39] INFO:     127.0.0.1:56925 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:39] INFO:     127.0.0.1:56922 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:39] INFO:     127.0.0.1:56919 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:39] INFO:     127.0.0.1:56920 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:39] INFO:     127.0.0.1:56924 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:58743 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:40] INFO:     127.0.0.1:58744 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:58748 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:58747 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:40] INFO:     127.0.0.1:58751 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:53411 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:53410 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:53406 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:53408 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:54531 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:54530 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:40] INFO:     127.0.0.1:53412 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:53407 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:54534 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:54536 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:40] INFO:     127.0.0.1:54538 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:50735 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:50737 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:50730 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:50729 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:50731 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:40] INFO:     127.0.0.1:50736 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:41] INFO:     127.0.0.1:51414 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:41] INFO:     127.0.0.1:51413 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:41] INFO:     127.0.0.1:51416 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:41] INFO:     127.0.0.1:51418 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:55:41] INFO:     127.0.0.1:51420 - "GET /api/companies HTTP/1.1" 200 OK
[20:55:41] INFO:     127.0.0.1:53236 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:41] INFO:     127.0.0.1:53232 - "GET /api/settings HTTP/1.1" 200 OK
[20:55:41] INFO:     127.0.0.1:53235 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:41] INFO:     127.0.0.1:53237 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:41] INFO:     127.0.0.1:53239 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:41] INFO:     127.0.0.1:53234 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:43] INFO:     127.0.0.1:58331 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:55:43] INFO:     127.0.0.1:58337 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:43] INFO:     127.0.0.1:58336 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:43] INFO:     127.0.0.1:58335 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:43] INFO:     127.0.0.1:58334 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:55:43] INFO:     127.0.0.1:50100 - "GET /api/hr/candidates/CAND-26907EAD HTTP/1.1" 200 OK
[20:55:43] INFO:     127.0.0.1:58338 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:43] INFO:     127.0.0.1:61334 - "GET /api/interview/room/candidates/CAND-26907EAD/runtime HTTP/1.1" 409 Conflict
[20:55:47] INFO:     127.0.0.1:60524 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:55:47] INFO:     127.0.0.1:60528 - "GET /api/departments HTTP/1.1" 200 OK
[20:55:47] INFO:     127.0.0.1:60527 - "GET /api/jobs HTTP/1.1" 200 OK
[20:55:47] INFO:     127.0.0.1:60526 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:55:47] INFO:     127.0.0.1:60525 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:56:18] INFO:     127.0.0.1:64597 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:56:18] INFO:     127.0.0.1:57415 - "GET /api/hr/candidates/CAND-26907EAD HTTP/1.1" 200 OK
[20:56:18] INFO:     127.0.0.1:52204 - "GET /api/interview/room/candidates/CAND-26907EAD/runtime HTTP/1.1" 409 Conflict
[20:56:18] INFO:     127.0.0.1:64603 - "GET /api/departments HTTP/1.1" 200 OK
[20:56:18] INFO:     127.0.0.1:64600 - "GET /api/jobs HTTP/1.1" 200 OK
[20:56:18] INFO:     127.0.0.1:64604 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:56:18] INFO:     127.0.0.1:64599 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:56:18] INFO:     127.0.0.1:64598 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:56:19] INFO:     127.0.0.1:57372 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:56:19] INFO:     127.0.0.1:57376 - "GET /api/departments HTTP/1.1" 200 OK
[20:56:19] INFO:     127.0.0.1:57375 - "GET /api/jobs HTTP/1.1" 200 OK
[20:56:19] INFO:     127.0.0.1:57374 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:56:19] INFO:     127.0.0.1:57373 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:56:19] INFO:     127.0.0.1:57377 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:56:22] INFO:     127.0.0.1:52426 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:56:22] INFO:     127.0.0.1:52427 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:56:22] INFO:     127.0.0.1:52431 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:56:22] INFO:     127.0.0.1:52430 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:56:22] INFO:     127.0.0.1:52433 - "GET /api/companies HTTP/1.1" 200 OK
[20:56:22] INFO:     127.0.0.1:51084 - "GET /api/settings HTTP/1.1" 200 OK
[20:56:22] INFO:     127.0.0.1:51092 - "GET /api/departments HTTP/1.1" 200 OK
[20:56:22] INFO:     127.0.0.1:51091 - "GET /api/jobs HTTP/1.1" 200 OK
[20:56:22] INFO:     127.0.0.1:51087 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:56:22] INFO:     127.0.0.1:51093 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:56:22] INFO:     127.0.0.1:51090 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:56:22] INFO:     127.0.0.1:56833 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:56:22] INFO:     127.0.0.1:56832 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:56:22] INFO:     127.0.0.1:56836 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:56:22] INFO:     127.0.0.1:56837 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:56:22] INFO:     127.0.0.1:56839 - "GET /api/companies HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:52989 - "GET /api/departments HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:52988 - "GET /api/jobs HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:52987 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:52985 - "GET /api/settings HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:52986 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:52990 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:61662 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:56:23] INFO:     127.0.0.1:61663 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:61666 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:56:23] INFO:     127.0.0.1:61667 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:61669 - "GET /api/companies HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:55821 - "GET /api/jobs HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:55822 - "GET /api/departments HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:55816 - "GET /api/settings HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:55817 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:54389 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:56:23] INFO:     127.0.0.1:54390 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:55823 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:55820 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:54709 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:54708 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:56:23] INFO:     127.0.0.1:54711 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:54713 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:56:23] INFO:     127.0.0.1:54715 - "GET /api/companies HTTP/1.1" 200 OK
[20:56:23] INFO:     127.0.0.1:64366 - "GET /api/jobs HTTP/1.1" 200 OK
[20:56:24] INFO:     127.0.0.1:64361 - "GET /api/settings HTTP/1.1" 200 OK
[20:56:24] INFO:     127.0.0.1:64367 - "GET /api/departments HTTP/1.1" 200 OK
[20:56:24] INFO:     127.0.0.1:64365 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:56:24] INFO:     127.0.0.1:64364 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:56:24] INFO:     127.0.0.1:64362 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:56:24] INFO:     127.0.0.1:62498 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:56:24] INFO:     127.0.0.1:62499 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:56:24] INFO:     127.0.0.1:62503 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:56:24] INFO:     127.0.0.1:62502 - "GET /api/interview/join/z05Rhlez7xKJXKeoZXSMgorMu5FN5KNHfqBUOLenEgL960OO_iwKR7NAaBLmOZYU HTTP/1.1" 404 Not Found
[20:56:24] INFO:     127.0.0.1:62505 - "GET /api/companies HTTP/1.1" 200 OK
[20:56:24] INFO:     127.0.0.1:51500 - "GET /api/departments HTTP/1.1" 200 OK
[20:56:24] INFO:     127.0.0.1:51496 - "GET /api/settings HTTP/1.1" 200 OK
[20:56:24] INFO:     127.0.0.1:51499 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:56:24] INFO:     127.0.0.1:51502 - "GET /api/jobs HTTP/1.1" 200 OK
[20:56:24] INFO:     127.0.0.1:51497 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:56:24] INFO:     127.0.0.1:51501 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:56:37] INFO:     127.0.0.1:58644 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:56:38] INFO:     127.0.0.1:58649 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:56:38] INFO:     127.0.0.1:58645 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:56:38] INFO:     127.0.0.1:58646 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:56:38] INFO:     127.0.0.1:58648 - "GET /api/departments HTTP/1.1" 200 OK
[20:56:38] INFO:     127.0.0.1:58647 - "GET /api/jobs HTTP/1.1" 200 OK
[20:56:39] INFO:     127.0.0.1:49275 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:56:39] INFO:     127.0.0.1:58985 - "GET /api/departments HTTP/1.1" 200 OK
[20:56:39] INFO:     127.0.0.1:58984 - "GET /api/jobs HTTP/1.1" 200 OK
[20:56:39] INFO:     127.0.0.1:58986 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:56:39] INFO:     127.0.0.1:58983 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:56:39] INFO:     127.0.0.1:60413 - "GET /api/hr/candidates/CAND-26907EAD HTTP/1.1" 200 OK
[20:56:39] INFO:     127.0.0.1:57619 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:56:39] INFO:     127.0.0.1:63070 - "GET /api/interview/room/candidates/CAND-26907EAD/runtime HTTP/1.1" 409 Conflict
[20:57:23] INFO:     127.0.0.1:57282 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:57:23] INFO:     127.0.0.1:62133 - "GET /api/departments HTTP/1.1" 200 OK
[20:57:23] INFO:     127.0.0.1:62132 - "GET /api/jobs HTTP/1.1" 200 OK
[20:57:23] INFO:     127.0.0.1:55719 - "GET /api/hr/candidates/CAND-26907EAD HTTP/1.1" 404 Not Found
[20:57:23] INFO:     127.0.0.1:62134 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:57:23] INFO:     127.0.0.1:62411 - "GET /api/interview/room/candidates/CAND-26907EAD/runtime HTTP/1.1" 404 Not Found
[20:57:23] INFO:     127.0.0.1:62127 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:57:23] INFO:     127.0.0.1:62128 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:57:26] INFO:     127.0.0.1:52188 - "GET /api/departments HTTP/1.1" 200 OK
[20:57:26] INFO:     127.0.0.1:52189 - "GET /api/hr/candidates/CAND-26907EAD HTTP/1.1" 404 Not Found
[20:57:26] INFO:     127.0.0.1:52186 - "GET /api/jobs HTTP/1.1" 200 OK
[20:57:26] INFO:     127.0.0.1:56903 - "GET /api/interview/room/candidates/CAND-26907EAD/runtime HTTP/1.1" 404 Not Found
[20:57:26] INFO:     127.0.0.1:52185 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:57:26] INFO:     127.0.0.1:52187 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:57:26] INFO:     127.0.0.1:52184 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:57:28] INFO:     127.0.0.1:59438 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:57:28] INFO:     127.0.0.1:59440 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:57:28] INFO:     127.0.0.1:59443 - "GET /api/hr/candidates/CAND-26907EAD HTTP/1.1" 404 Not Found
[20:57:28] INFO:     127.0.0.1:59447 - "GET /api/hr/candidates/CAND-26907EAD HTTP/1.1" 404 Not Found
[20:57:28] INFO:     127.0.0.1:59444 - "GET /api/companies HTTP/1.1" 200 OK
[20:57:28] INFO:     127.0.0.1:60883 - "GET /api/departments HTTP/1.1" 200 OK
[20:57:28] INFO:     127.0.0.1:60878 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:57:28] INFO:     127.0.0.1:60879 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:57:28] INFO:     127.0.0.1:60882 - "GET /api/jobs HTTP/1.1" 200 OK
[20:57:28] INFO:     127.0.0.1:60881 - "GET /api/settings HTTP/1.1" 200 OK
[20:57:28] INFO:     127.0.0.1:60880 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:57:28] INFO:     127.0.0.1:65334 - "GET /api/hr/candidates/CAND-26907EAD HTTP/1.1" 404 Not Found
[20:57:28] INFO:     127.0.0.1:61047 - "GET /api/hr/candidates/CAND-26907EAD HTTP/1.1" 404 Not Found
[20:57:30] INFO:     127.0.0.1:53963 - "GET /api/hr/candidates?status=shortlisted HTTP/1.1" 200 OK
[20:57:30] INFO:     127.0.0.1:63087 - "GET /api/hr/candidates?status=shortlisted HTTP/1.1" 200 OK
[20:57:30] INFO:     127.0.0.1:49675 - "GET /api/hr/candidates?status=shortlisted HTTP/1.1" 200 OK
[20:57:30] INFO:     127.0.0.1:61969 - "GET /api/hr/candidates?status=shortlisted HTTP/1.1" 200 OK
[20:57:32] INFO:     127.0.0.1:51621 - "GET /api/departments HTTP/1.1" 200 OK
[20:57:32] INFO:     127.0.0.1:51620 - "GET /api/jobs HTTP/1.1" 200 OK
[20:57:32] INFO:     127.0.0.1:51618 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:57:32] INFO:     127.0.0.1:51622 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:57:32] INFO:     127.0.0.1:51619 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:57:41] INFO:     127.0.0.1:54972 - "GET /api/departments HTTP/1.1" 200 OK
[20:57:41] INFO:     127.0.0.1:54971 - "GET /api/jobs HTTP/1.1" 200 OK
[20:57:41] INFO:     127.0.0.1:54974 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:57:41] INFO:     127.0.0.1:54970 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:57:41] INFO:     127.0.0.1:54969 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:57:48] INFO:     127.0.0.1:52798 - "POST /extract/async HTTP/1.1" 202 Accepted
[20:57:48] INFO:     127.0.0.1:52357 - "GET /api/candidates/evaluate/jobs/a2e529b5-9819-44c2-8254-a7ddd353ed43 HTTP/1.1" 200 OK
[20:57:49] 2026-11-17 20:57:48,770 | INFO | agents.screening_agent.services.docling_extractor | Docling PDF extraction started (OCR mode: auto)
[20:57:49] 2026-11-17 20:57:48,800 | INFO | docling.datamodel.document | detected formats: [<InputFormat.PDF: 'pdf'>]
[20:57:49] 2026-11-17 20:57:48,817 | INFO | docling.document_converter | Going to convert document batch...
[20:57:49] 2026-11-17 20:57:48,817 | INFO | docling.pipeline.base_pipeline | Processing document 9a0f70deb2ac40dd9dc23e7667156875.pdf
[20:57:50] INFO:     127.0.0.1:60944 - "GET /api/candidates/evaluate/jobs/a2e529b5-9819-44c2-8254-a7ddd353ed43 HTTP/1.1" 200 OK
[20:57:53] INFO:     127.0.0.1:53993 - "GET /api/candidates/evaluate/jobs/a2e529b5-9819-44c2-8254-a7ddd353ed43 HTTP/1.1" 200 OK
[20:57:55] INFO:     127.0.0.1:62626 - "GET /api/candidates/evaluate/jobs/a2e529b5-9819-44c2-8254-a7ddd353ed43 HTTP/1.1" 200 OK
[20:57:55] 2026-11-17 20:57:55,214 | INFO | docling.document_converter | Finished converting document 9a0f70deb2ac40dd9dc23e7667156875.pdf in 6.44 sec.
[20:57:55] 2026-11-17 20:57:55,281 | INFO | agents.screening_agent.services.docling_extractor | PDF conversion succeeded using the embedded text layer
[20:57:57] INFO:     127.0.0.1:54996 - "GET /api/candidates/evaluate/jobs/a2e529b5-9819-44c2-8254-a7ddd353ed43 HTTP/1.1" 200 OK
[20:57:57] INFO:     127.0.0.1:50206 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:57:57] INFO:     127.0.0.1:50209 - "GET /api/departments HTTP/1.1" 200 OK
[20:57:57] INFO:     127.0.0.1:50208 - "GET /api/jobs HTTP/1.1" 200 OK
[20:57:58] INFO:     127.0.0.1:50211 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:57:58] INFO:     127.0.0.1:50207 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:57:59] INFO:     127.0.0.1:59311 - "GET /api/candidates/evaluate/jobs/a2e529b5-9819-44c2-8254-a7ddd353ed43 HTTP/1.1" 200 OK
[20:58:01] INFO:     127.0.0.1:50369 - "GET /api/candidates/evaluate/jobs/a2e529b5-9819-44c2-8254-a7ddd353ed43 HTTP/1.1" 200 OK
[20:58:04] INFO:     127.0.0.1:62940 - "GET /api/candidates/evaluate/jobs/a2e529b5-9819-44c2-8254-a7ddd353ed43 HTTP/1.1" 200 OK
[20:58:06] 2026-11-17 20:58:05,120 | INFO | httpx | HTTP Request: POST https://interview-openai-foundr-resource.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-10-21 "HTTP/1.1 200 OK"
[20:58:06] 2026-11-17 20:58:05,187 | INFO | agents.screening_agent.services.screening_job_runner | Extract job a2e529b5-9819-44c2-8254-a7ddd353ed43 parsed Ravi_Molake_Resume_office 1.pdf; scoring job 0705f2f9-6f19-47cf-b7de-2ade85fd0425 queued
[20:58:06] INFO:     127.0.0.1:56635 - "GET /api/candidates/evaluate/jobs/a2e529b5-9819-44c2-8254-a7ddd353ed43 HTTP/1.1" 200 OK
[20:58:06] INFO:     127.0.0.1:54272 - "GET /api/candidates/evaluate/jobs/0705f2f9-6f19-47cf-b7de-2ade85fd0425 HTTP/1.1" 200 OK
[20:58:06] 2026-11-17 20:58:05,765 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='Python' | Resume='Python' | Similarity=1.000 | Status=Perfect Match | Level=EXACT_MATCH | Method=exact
[20:58:06] 2026-11-17 20:58:05,779 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='Object-Oriented Programming (OOP)' | Resume='Object-Oriented Programming' | Similarity=0.926 | Status=Perfect Match | Level=STRONG_SEMANTIC_MATCH | Method=semantic
[20:58:06] 2026-11-17 20:58:05,781 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='FastAPI' | Resume='FastAPI' | Similarity=1.000 | Status=Perfect Match | Level=EXACT_MATCH | Method=exact
[20:58:06] 2026-11-17 20:58:05,781 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='Flask' | Resume='Flask' | Similarity=1.000 | Status=Perfect Match | Level=EXACT_MATCH | Method=exact
[20:58:06] 2026-11-17 20:58:05,781 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='TensorFlow' | Resume='TensorFlow' | Similarity=1.000 | Status=Perfect Match | Level=EXACT_MATCH | Method=exact
[20:58:06] 2026-11-17 20:58:05,781 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='PyTorch' | Resume='PyTorch' | Similarity=1.000 | Status=Perfect Match | Level=EXACT_MATCH | Method=exact
[20:58:06] 2026-11-17 20:58:05,781 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='NumPy' | Resume='NumPy' | Similarity=1.000 | Status=Perfect Match | Level=EXACT_MATCH | Method=exact
[20:58:06] 2026-11-17 20:58:05,783 | INFO | agents.screening_agent.services.semantic_matching_service | Semantic skill match | JD='Machine Learning Algorithms' | Resume='Machine Learning' | Similarity=0.937 | Status=Perfect Match | Level=STRONG_SEMANTIC_MATCH | Method=semantic
[20:58:11] INFO:     127.0.0.1:65284 - "GET /api/candidates/evaluate/jobs/0705f2f9-6f19-47cf-b7de-2ade85fd0425 HTTP/1.1" 200 OK
[20:58:16] 2026-11-17 20:58:15,492 | INFO | services.screening_integration_service | Re-screened existing candidate CAND-BB90FF6E for same JD — preserved interview/proctoring history
[20:58:16] INFO:     127.0.0.1:60515 - "GET /api/jobs HTTP/1.1" 200 OK
[20:58:16] 2026-11-17 20:58:15,652 | INFO | agents.scheduler_agent.nodes | Scheduling invite link for CAND-BB90FF6E: http://localhost:5173/schedule/d4dde4e5-b3fc-412b-b4f4-b279d2288e13
[20:58:16] INFO:     127.0.0.1:60517 - "GET /api/departments HTTP/1.1" 200 OK
[20:58:16] INFO:     127.0.0.1:61833 - "GET /api/candidates/evaluate/jobs/0705f2f9-6f19-47cf-b7de-2ade85fd0425 HTTP/1.1" 200 OK
[20:58:16] INFO:     127.0.0.1:60513 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:58:16] INFO:     127.0.0.1:60512 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:58:16] INFO:     127.0.0.1:60518 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:58:18] INFO:     127.0.0.1:59942 - "GET /api/candidates/evaluate/jobs/0705f2f9-6f19-47cf-b7de-2ade85fd0425 HTTP/1.1" 200 OK
[20:58:18] 2026-11-17 20:58:18,103 | INFO | agents.scheduler_agent.nodes | Interview slots synced: created=0 removed=0 total=1368
[20:58:20] 2026-11-17 20:58:19,576 | INFO | services.email_service | Email sent via SMTP to=ravi.molake@rrglobal.com subject=RR Kabel | Your Resume Has Been Shortlisted
[20:58:21] 2026-11-17 20:58:20,492 | INFO | services.screening_integration_service | Shortlisted candidate CAND-BB90FF6E (ravi.molake@rrglobal.com) — invite sent, token=d4dde4e5-b3fc-412b-b4f4-b279d2288e13
[20:58:21] INFO:     127.0.0.1:58585 - "GET /api/candidates/evaluate/jobs/0705f2f9-6f19-47cf-b7de-2ade85fd0425 HTTP/1.1" 200 OK
[20:58:21] INFO:     127.0.0.1:63225 - "GET /api/departments HTTP/1.1" 200 OK
[20:58:21] INFO:     127.0.0.1:63224 - "GET /api/jobs HTTP/1.1" 200 OK
[20:58:21] INFO:     127.0.0.1:63218 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:58:21] INFO:     127.0.0.1:63226 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:58:21] INFO:     127.0.0.1:63223 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:58:33] INFO:     127.0.0.1:59689 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:58:33] INFO:     127.0.0.1:59693 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:58:34] INFO:     127.0.0.1:59695 - "GET /api/companies HTTP/1.1" 200 OK
[20:58:35] INFO:     127.0.0.1:61456 - "GET /api/departments HTTP/1.1" 200 OK
[20:58:35] INFO:     127.0.0.1:61455 - "GET /api/jobs HTTP/1.1" 200 OK
[20:58:35] INFO:     127.0.0.1:61451 - "GET /api/settings HTTP/1.1" 200 OK
[20:58:35] INFO:     127.0.0.1:61454 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:58:35] INFO:     127.0.0.1:61453 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:58:35] INFO:     127.0.0.1:54641 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:58:37] INFO:     127.0.0.1:59687 - "GET /api/interview/token/d4dde4e5-b3fc-412b-b4f4-b279d2288e13 HTTP/1.1" 200 OK
[20:58:39] INFO:     127.0.0.1:63675 - "GET /api/interview/token/d4dde4e5-b3fc-412b-b4f4-b279d2288e13 HTTP/1.1" 200 OK
[20:58:42] 2026-11-17 20:58:42,137 | INFO | services.email_service | Email sent via SMTP to=ravi.molake@rrglobal.com subject=RR Kabel | Interview Scheduled Successfully
[20:58:46] 2026-11-17 20:58:46,635 | INFO | httpx | HTTP Request: POST https://interview-openai-foundr-resource.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-10-21 "HTTP/1.1 200 OK"
[20:58:46] 2026-11-17 20:58:46,635 | INFO | agents.blueprint_agent.scenario_plan | Agent 3 refined 8 scenario intents with LLM (gpt-4o)
[20:58:54] 2026-11-17 20:58:53,436 | INFO | httpx | HTTP Request: POST https://interview-openai-foundr-resource.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-10-21 "HTTP/1.1 200 OK"
[20:58:58] 2026-11-17 20:58:57,166 | INFO | httpx | HTTP Request: POST https://interview-openai-foundr-resource.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-10-21 "HTTP/1.1 200 OK"
[20:58:58] 2026-11-17 20:58:57,174 | INFO | agents.interview_agent.adaptive | Agent 4 generated questions via LLM (8/8 from model gpt-4o)
[20:59:02] INFO:     127.0.0.1:59464 - "POST /api/interview/book-slot HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:56814 - "GET /api/departments HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:56816 - "GET /api/jobs HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:59671 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:56817 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:57490 - "GET /api/auth/me HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:56813 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:56812 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:64404 - "GET /api/companies HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:59282 - "GET /api/departments HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:59274 - "GET /api/settings HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:59281 - "GET /api/jobs HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:59280 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:63661 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:59279 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[20:59:03] 2026-11-17 20:59:02,664 | INFO | api.routes.interview | Interview join bootstrap candidate=CAND-BB90FF6E role=candidate elapsed_ms=237
[20:59:03] INFO:     127.0.0.1:59669 - "GET /api/interview/join/puDzb0azEZ8CCSO7T4K8EbPhi5XTOLfhZNvQ330uHu6v-eYM6lMP7WOOnA7jLAJl HTTP/1.1" 200 OK
[20:59:03] 2026-11-17 20:59:02,831 | INFO | api.routes.interview | Interview join bootstrap candidate=CAND-BB90FF6E role=candidate elapsed_ms=76
[20:59:03] INFO:     127.0.0.1:59005 - "GET /api/interview/join/puDzb0azEZ8CCSO7T4K8EbPhi5XTOLfhZNvQ330uHu6v-eYM6lMP7WOOnA7jLAJl HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:61624 - "GET /proctoring/?session_id=3864d33e-fc1e-4d68-8416-d72d0c60cb4d&token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMDFhM2JhOC1jYmNlLTRmMzktYjA2Ni1lMmJhNTJjZWU1NWMiLCJ0eXAiOiJjYW5kaWRhdGUiLCJpYXQiOjE3OTQ5MjkzNDIsImV4cCI6MTc5NDk3MjU0Miwic2Vzc2lvbl9pZCI6IjM4NjRkMzNlLWZjMWUtNGQ2OC04NDE2LWQ3MmQwYzYwY2I0ZCIsInJyX2NhbmRpZGF0ZV9pZCI6IkNBTkQtQkI5MEZGNkUiLCJwYXJ0aWNpcGFudF9
[20:59:03] INFO:     127.0.0.1:50964 - "GET /api/runtime-config HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:52819 - "GET /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/state HTTP/1.1" 200 OK
[20:59:03] INFO:     127.0.0.1:62846 - "GET /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/runtime HTTP/1.1" 200 OK
[20:59:13] INFO:     127.0.0.1:51130 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/device-check HTTP/1.1" 200 OK
[20:59:13] INFO:     127.0.0.1:54435 - "GET /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/voice/sentence HTTP/1.1" 200 OK
[20:59:16] INFO:     127.0.0.1:62891 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/face/enroll HTTP/1.1" 200 OK
[20:59:23] INFO:     127.0.0.1:57937 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/face/enroll HTTP/1.1" 200 OK
[20:59:25] INFO:     127.0.0.1:53253 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/face/enroll HTTP/1.1" 200 OK
[20:59:28] INFO:     127.0.0.1:54616 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/face/enroll HTTP/1.1" 200 OK
[20:59:29] INFO:     127.0.0.1:50638 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/face/verify HTTP/1.1" 200 OK
[20:59:33] INFO:     127.0.0.1:50356 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/voice/sentence/change HTTP/1.1" 200 OK
[20:59:35] INFO:     127.0.0.1:49817 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/voice/sentence/change HTTP/1.1" 200 OK
[20:59:43] 2026-11-17 20:59:42,175 | INFO | agents.shared.azure_http | Azure httpx client ready (name=speech, max_connections=32)
[20:59:45] 2026-11-17 20:59:44,310 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[20:59:49] INFO:     127.0.0.1:59693 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/voice/enroll HTTP/1.1" 200 OK
[20:59:52] INFO:     127.0.0.1:58418 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/start HTTP/1.1" 200 OK
[20:59:52] INFO:     127.0.0.1:65414 - "WebSocket /ws/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMDFhM2JhOC1jYmNlLTRmMzktYjA2Ni1lMmJhNTJjZWU1NWMiLCJ0eXAiOiJjYW5kaWRhdGUiLCJpYXQiOjE3OTQ5MjkzNDIsImV4cCI6MTc5NDk3MjU0Miwic2Vzc2lvbl9pZCI6IjM4NjRkMzNlLWZjMWUtNGQ2OC04NDE2LWQ3MmQwYzYwY2I0ZCIsInJyX2NhbmRpZGF0ZV9pZCI6IkNBTkQtQkI5MEZGNkUiLCJwYXJ0aWNpcGFudF9yb2xl
[20:59:52] INFO:     connection open
[20:59:52] INFO:     127.0.0.1:58737 - "GET /proctoring/pcm-worklet.js HTTP/1.1" 404 Not Found
[20:59:57] 2026-11-17 20:59:56,677 | INFO | httpx | HTTP Request: POST https://interview-openai-foundr-resource.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-10-21 "HTTP/1.1 200 OK"
[20:59:58] INFO:     127.0.0.1:65413 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/start HTTP/1.1" 200 OK
[20:59:58] INFO:     127.0.0.1:52083 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[20:59:58] INFO:     127.0.0.1:59368 - "GET /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/runtime HTTP/1.1" 200 OK
[21:00:02] INFO:     127.0.0.1:59238 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:00:02] 2026-11-17 21:00:02,322 | INFO | httpx | HTTP Request: POST https://interview-openai-foundr-resource.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-10-21 "HTTP/1.1 200 OK"
[21:00:02] 2026-11-17 21:00:02,322 | INFO | services.interview_mcq_service | MCQ generation finished candidate=CAND-BB90FF6E questions=8 elapsed_ms=4250
[21:00:02] INFO:     127.0.0.1:57808 - "GET /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/mcq HTTP/1.1" 200 OK
[21:00:02] INFO:     127.0.0.1:50681 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/speak-stream HTTP/1.1" 200 OK
[21:00:05] 2026-11-17 21:00:05,800 | INFO | agents.interview_agent.streaming_tts | TTS stream done voice=en-IN-PrabhatIndicNeural bytes=389952 ttfa_ms=1612.3 total_ms=3292
[21:00:07] INFO:     127.0.0.1:52110 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:00:13] INFO:     127.0.0.1:52113 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:00:18] INFO:     127.0.0.1:53356 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:00:22] INFO:     127.0.0.1:49820 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:00:27] INFO:     127.0.0.1:50767 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:00:29] INFO:     127.0.0.1:57647 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/speak-stream HTTP/1.1" 200 OK
[21:00:32] INFO:     127.0.0.1:60766 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:00:32] 2026-11-17 21:00:32,547 | INFO | agents.interview_agent.streaming_tts | TTS stream done voice=en-IN-PrabhatIndicNeural bytes=374400 ttfa_ms=1679.9 total_ms=3199
[21:00:38] INFO:     127.0.0.1:50261 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:00:43] INFO:     127.0.0.1:65521 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:00:48] INFO:     127.0.0.1:60091 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:00:52] INFO:     127.0.0.1:60938 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:00:54] 2026-11-17 21:00:54,673 | INFO | services.interview_mcq_service | MCQ start candidate=CAND-BB90FF6E status=in_progress elapsed_ms=13
[21:00:54] INFO:     127.0.0.1:54624 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/mcq/start HTTP/1.1" 200 OK
[21:00:57] INFO:     127.0.0.1:52728 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:00:59] E0000 00:00:1794929458.372257   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T15:44:58.367871883+00:00
[21:00:59] === Source Location Trace: === 
[21:00:59] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[21:01:01] INFO:     127.0.0.1:53897 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/mcq/answer HTTP/1.1" 200 OK
[21:01:03] INFO:     127.0.0.1:60446 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/mcq/answer HTTP/1.1" 200 OK
[21:01:03] INFO:     127.0.0.1:56566 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:01:03] INFO:     127.0.0.1:50088 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/mcq/answer HTTP/1.1" 200 OK
[21:01:04] INFO:     127.0.0.1:55754 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/mcq/answer HTTP/1.1" 200 OK
[21:01:05] INFO:     127.0.0.1:61901 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/mcq/answer HTTP/1.1" 200 OK
[21:01:06] INFO:     127.0.0.1:54307 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/mcq/answer HTTP/1.1" 200 OK
[21:01:07] INFO:     127.0.0.1:63639 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/mcq/answer HTTP/1.1" 200 OK
[21:01:08] INFO:     127.0.0.1:56355 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/mcq/answer HTTP/1.1" 200 OK
[21:01:08] INFO:     127.0.0.1:65274 - "GET /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/session HTTP/1.1" 200 OK
[21:01:08] INFO:     127.0.0.1:58757 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:01:08] INFO:     127.0.0.1:59924 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/speak-stream HTTP/1.1" 200 OK
[21:01:11] 2026-11-17 21:01:10,949 | INFO | agents.interview_agent.streaming_tts | TTS stream done voice=en-IN-PrabhatIndicNeural bytes=441216 ttfa_ms=1695.6 total_ms=3038
[21:01:13] INFO:     127.0.0.1:57899 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:01:18] INFO:     127.0.0.1:51983 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:01:24] INFO:     127.0.0.1:58944 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:01:29] INFO:     connection closed
[21:01:30] INFO:     127.0.0.1:51356 - "GET /api/auth/me HTTP/1.1" 200 OK
[21:01:30] INFO:     127.0.0.1:51360 - "GET /api/departments HTTP/1.1" 200 OK
[21:01:30] INFO:     127.0.0.1:51361 - "GET /api/jobs HTTP/1.1" 200 OK
[21:01:30] INFO:     127.0.0.1:50750 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[21:01:30] INFO:     127.0.0.1:51359 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[21:01:30] INFO:     127.0.0.1:51358 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
