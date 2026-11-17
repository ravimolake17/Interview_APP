# Interview test log

Recording started 2026-11-17 21:03:28

```
[21:03:30] INFO:     127.0.0.1:55731 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:03:36] INFO:     127.0.0.1:61348 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:03:38] INFO:     127.0.0.1:58911 - "WebSocket /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/stt-stream?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMDFhM2JhOC1jYmNlLTRmMzktYjA2Ni1lMmJhNTJjZWU1NWMiLCJ0eXAiOiJjYW5kaWRhdGUiLCJpYXQiOjE3OTQ5Mjk1NjgsImV4cCI6MTc5NDk3Mjc2OCwic2Vzc2lvbl9pZCI6IjM4NjRkMzNlLWZjMWUtNGQ2OC04NDE2LWQ3MmQwYzYwY2I0ZCIsInJyX2NhbmRpZGF0ZV9pZCI6IkNBTkQtQkI5ME
[21:03:38] INFO:     connection open
[21:03:38] 2026-11-17 21:03:37,200 | INFO | api.routes.candidate_interview_stt_ws | streaming_stt_turn_start session=3864d33e-fc1e-4d68-8416-d72d0c60cb4d question=q-ef388c8059
[21:03:38] INFO:     127.0.0.1:65431 - "GET /proctoring/pcm-worklet.js HTTP/1.1" 404 Not Found
[21:03:38] 2026-11-17 21:03:37,336 | INFO | api.routes.candidate_interview_stt_ws | streaming_stt_socket_closed session=3864d33e-fc1e-4d68-8416-d72d0c60cb4d started=True frames=0 bytes=0
[21:03:38] INFO:     connection closed
[21:03:41] 2026-11-17 21:03:40,688 | INFO | agents.interview_agent.stt_executor | STT executor started (max_workers=4)
[21:03:41] INFO:     127.0.0.1:49177 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:03:43] 2026-11-17 21:03:42,670 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:03:43] 2026-11-17 21:03:42,670 | INFO | interview.latency | {"event":"interview_latency","turn_id":"96c8e047c81b4b1aa655425434701f20","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":2008.64,"metrics":{"audio_receive_ms":0.046,"audio_bytes":48494,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","database
[21:03:43] INFO:     127.0.0.1:54511 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:03:44] INFO:     127.0.0.1:62765 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/tab-switch HTTP/1.1" 200 OK
[21:03:45] 2026-11-17 21:03:45,344 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:03:45] 2026-11-17 21:03:45,363 | INFO | interview.latency | {"event":"interview_latency","turn_id":"8eda900018934c6e89e76befa103d908","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":1550.201,"metrics":{"audio_receive_ms":0.056,"audio_bytes":97808,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databas
[21:03:45] INFO:     127.0.0.1:49672 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:03:46] INFO:     127.0.0.1:51234 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:03:49] 2026-11-17 21:03:48,626 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:03:49] 2026-11-17 21:03:48,631 | INFO | interview.latency | {"event":"interview_latency","turn_id":"7bfa3341afad46cf951d17c32ea0adda","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":2156.686,"metrics":{"audio_receive_ms":0.058,"audio_bytes":147122,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:03:49] INFO:     127.0.0.1:60704 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:03:51] INFO:     127.0.0.1:53374 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:03:52] 2026-11-17 21:03:52,211 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:03:52] 2026-11-17 21:03:52,211 | INFO | interview.latency | {"event":"interview_latency","turn_id":"46f9aa9df72d484f9a0566849caf4072","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":2698.554,"metrics":{"audio_receive_ms":0.081,"audio_bytes":196436,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:03:52] INFO:     127.0.0.1:64204 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:03:55] 2026-11-17 21:03:55,535 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:03:55] 2026-11-17 21:03:55,535 | INFO | interview.latency | {"event":"interview_latency","turn_id":"6cc9f458c0194ba9838b8b7a71a0cc7a","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":3101.531,"metrics":{"audio_receive_ms":0.127,"audio_bytes":245750,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:03:55] INFO:     127.0.0.1:63832 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:03:55] INFO:     127.0.0.1:59561 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:03:59] E0000 00:00:1794929638.390620   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T15:44:58.367871883+00:00
[21:03:59] === Source Location Trace: === 
[21:03:59] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[21:04:01] INFO:     127.0.0.1:50855 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:04:03] 2026-11-17 21:04:02,798 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:04:03] 2026-11-17 21:04:02,804 | INFO | interview.latency | {"event":"interview_latency","turn_id":"2113f579134a4bef8cf47c71aaacc1b6","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":4136.042,"metrics":{"audio_receive_ms":0.112,"audio_bytes":344378,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:04:03] INFO:     127.0.0.1:55256 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:04:06] INFO:     127.0.0.1:62636 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:04:10] 2026-11-17 21:04:10,128 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:04:10] 2026-11-17 21:04:10,130 | INFO | interview.latency | {"event":"interview_latency","turn_id":"2c98bd886a1b4c26bc0fded2930b347f","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":5164.968,"metrics":{"audio_receive_ms":0.191,"audio_bytes":426568,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:04:10] INFO:     127.0.0.1:60849 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:04:11] INFO:     127.0.0.1:54661 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:04:17] INFO:     127.0.0.1:65318 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:04:17] 2026-11-17 21:04:16,510 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:04:17] 2026-11-17 21:04:16,520 | INFO | interview.latency | {"event":"interview_latency","turn_id":"beb5711b6458430992177f5568f30cc9","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":6006.746,"metrics":{"audio_receive_ms":0.194,"audio_bytes":525196,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:04:17] INFO:     127.0.0.1:54971 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:04:21] INFO:     127.0.0.1:50840 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:04:27] INFO:     127.0.0.1:57541 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:04:28] 2026-11-17 21:04:27,428 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:04:28] 2026-11-17 21:04:27,428 | INFO | interview.latency | {"event":"interview_latency","turn_id":"912f63fede0a4cbaa2dee3fdfbb1030d","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":7697.906,"metrics":{"audio_receive_ms":0.214,"audio_bytes":673138,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:04:28] INFO:     127.0.0.1:50708 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:04:29] 2026-11-17 21:04:28,788 | INFO | agents.interview_agent.stt_service | Azure STT chunking 50.9s audio into 2 parts for complete transcript
[21:04:31] INFO:     127.0.0.1:59700 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:04:36] INFO:     127.0.0.1:55573 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:04:36] 2026-11-17 21:04:36,848 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:04:39] 2026-11-17 21:04:38,494 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:04:39] 2026-11-17 21:04:38,498 | INFO | interview.latency | {"event":"interview_latency","turn_id":"e57e21c8ce0a439c9fc0cf17ffa1f15c","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":9964.175,"metrics":{"audio_receive_ms":0.251,"audio_bytes":821080,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:04:39] INFO:     127.0.0.1:52593 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:04:42] INFO:     127.0.0.1:50035 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:04:46] INFO:     127.0.0.1:58297 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:04:51] INFO:     127.0.0.1:61748 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:04:56] INFO:     127.0.0.1:56274 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:04:58] E0000 00:00:1794929698.404674   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T15:44:58.367871883+00:00
[21:04:58] === Source Location Trace: === 
[21:04:58] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[21:05:02] INFO:     127.0.0.1:60097 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:05:07] INFO:     127.0.0.1:55418 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:05:11] INFO:     127.0.0.1:63739 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:05:16] INFO:     127.0.0.1:57316 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:05:22] INFO:     127.0.0.1:56393 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:05:27] INFO:     127.0.0.1:60602 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:05:32] INFO:     127.0.0.1:51829 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:05:37] INFO:     127.0.0.1:53615 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:05:40] 2026-11-17 21:05:40,065 | INFO | agents.interview_agent.stt_service | Azure STT chunking 122.2s audio into 3 parts for complete transcript
[21:05:41] INFO:     127.0.0.1:57065 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:05:47] INFO:     127.0.0.1:59121 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:05:49] 2026-11-17 21:05:48,827 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:05:52] INFO:     127.0.0.1:65476 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:05:57] 2026-11-17 21:05:56,777 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:05:57] INFO:     127.0.0.1:56569 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:05:58] E0000 00:00:1794929758.405860   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T15:44:58.367871883+00:00
[21:05:58] === Source Location Trace: === 
[21:05:58] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[21:06:02] INFO:     127.0.0.1:50890 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:06:02] 2026-11-17 21:06:02,770 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:06:05] 2026-11-17 21:06:05,691 | INFO | interview.latency | {"event":"interview_latency","turn_id":"93f615e5146b421e9eca3b8201d28dc0","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe","elapsed_ms":26009.997,"metrics":{"audio_receive_ms":4.087,"audio_bytes":1969862,"database_save_ms":86.115},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms"],"events":[
[21:06:05] INFO:     127.0.0.1:57761 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:06:05] 2026-11-17 21:06:05,848 | INFO | interview.latency | {"event":"interview_latency","turn_id":"93f615e5146b421e9eca3b8201d28dc0","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"answer","elapsed_ms":84.671,"metrics":{"redis_enqueue_ms":0.145,"langgraph_ms":29.838,"database_save_ms":47.432,"answer_api_ms":81.924},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio
[21:06:05] INFO:     127.0.0.1:62608 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/answer HTTP/1.1" 200 OK
[21:06:06] INFO:     127.0.0.1:53116 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/speak-stream HTTP/1.1" 200 OK
[21:06:08] INFO:     127.0.0.1:56208 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:06:09] 2026-11-17 21:06:08,446 | INFO | agents.interview_agent.streaming_tts | TTS stream done voice=en-IN-PrabhatIndicNeural bytes=163008 ttfa_ms=1734.9 total_ms=2476
[21:06:12] INFO:     127.0.0.1:54029 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:06:17] INFO:     127.0.0.1:64333 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:06:19] 2026-11-17 21:06:18,450 | INFO | interview.latency | {"event":"interview_latency","turn_id":"93f615e5146b421e9eca3b8201d28dc0","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"client_turn_complete","elapsed_ms":0.089,"metrics":{"audio_input_sample_rate":48000.0,"silence_wait_ms":2519.9,"answer_recorded_ms":122273.0,"audio_upload_ms":26570.9,"transcribe_request_ms":26570.9,"stt_mode_eff
[21:06:19] INFO:     127.0.0.1:51525 - "WebSocket /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/stt-stream?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMDFhM2JhOC1jYmNlLTRmMzktYjA2Ni1lMmJhNTJjZWU1NWMiLCJ0eXAiOiJjYW5kaWRhdGUiLCJpYXQiOjE3OTQ5Mjk1NjgsImV4cCI6MTc5NDk3Mjc2OCwic2Vzc2lvbl9pZCI6IjM4NjRkMzNlLWZjMWUtNGQ2OC04NDE2LWQ3MmQwYzYwY2I0ZCIsInJyX2NhbmRpZGF0ZV9pZCI6IkNBTkQtQkI5ME
[21:06:19] INFO:     127.0.0.1:51523 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/latency-beacon HTTP/1.1" 200 OK
[21:06:19] INFO:     connection open
[21:06:19] 2026-11-17 21:06:18,488 | INFO | api.routes.candidate_interview_stt_ws | streaming_stt_turn_start session=3864d33e-fc1e-4d68-8416-d72d0c60cb4d question=q-2ad5d57222
[21:06:19] INFO:     127.0.0.1:51161 - "GET /proctoring/pcm-worklet.js HTTP/1.1" 404 Not Found
[21:06:19] 2026-11-17 21:06:18,594 | INFO | api.routes.candidate_interview_stt_ws | streaming_stt_socket_closed session=3864d33e-fc1e-4d68-8416-d72d0c60cb4d started=True frames=0 bytes=0
[21:06:19] INFO:     connection closed
[21:06:22] INFO:     127.0.0.1:55862 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:06:23] 2026-11-17 21:06:23,020 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:06:23] 2026-11-17 21:06:23,020 | INFO | interview.latency | {"event":"interview_latency","turn_id":"15462e4991eb482e8dc596aff95e238a","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":1030.108,"metrics":{"audio_receive_ms":0.047,"audio_bytes":48494,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databas
[21:06:23] INFO:     127.0.0.1:54705 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:06:26] 2026-11-17 21:06:26,348 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:06:26] 2026-11-17 21:06:26,348 | INFO | interview.latency | {"event":"interview_latency","turn_id":"0d8e75f31d3041fc9694b98f1168a1f9","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":1538.008,"metrics":{"audio_receive_ms":0.055,"audio_bytes":97808,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databas
[21:06:26] INFO:     127.0.0.1:52290 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:06:27] INFO:     127.0.0.1:50852 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:06:29] 2026-11-17 21:06:29,768 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:06:29] 2026-11-17 21:06:29,773 | INFO | interview.latency | {"event":"interview_latency","turn_id":"4f7cef1562804149a2e5cc710c59110c","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":2037.695,"metrics":{"audio_receive_ms":0.067,"audio_bytes":147122,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:06:29] INFO:     127.0.0.1:63209 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:06:33] INFO:     127.0.0.1:64354 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:06:34] 2026-11-17 21:06:33,478 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:06:34] 2026-11-17 21:06:33,478 | INFO | interview.latency | {"event":"interview_latency","turn_id":"d64af5ce4990457b99d2f28d439add1e","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":2582.939,"metrics":{"audio_receive_ms":0.141,"audio_bytes":196436,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:06:34] INFO:     127.0.0.1:59317 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:06:37] 2026-11-17 21:06:36,758 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:06:37] 2026-11-17 21:06:36,758 | INFO | interview.latency | {"event":"interview_latency","turn_id":"2217137b53a84c20b0f2e228c98a4fa8","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":3098.426,"metrics":{"audio_receive_ms":0.088,"audio_bytes":245750,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:06:37] INFO:     127.0.0.1:55462 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:06:37] INFO:     127.0.0.1:54067 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:06:42] INFO:     127.0.0.1:63501 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:06:44] 2026-11-17 21:06:44,028 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:06:44] 2026-11-17 21:06:44,028 | INFO | interview.latency | {"event":"interview_latency","turn_id":"1a23330d738b4a69b9653b2393dec84a","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":4086.562,"metrics":{"audio_receive_ms":0.141,"audio_bytes":344378,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:06:44] INFO:     127.0.0.1:51050 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:06:47] INFO:     127.0.0.1:59459 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:06:50] 2026-11-17 21:06:50,359 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:06:50] 2026-11-17 21:06:50,563 | INFO | interview.latency | {"event":"interview_latency","turn_id":"9a6340e0f8f5418186e705a2e2fde39e","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe","elapsed_ms":5202.746,"metrics":{"audio_receive_ms":0.136,"audio_bytes":434311,"database_save_ms":35.844},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms"],"events":["a
[21:06:50] INFO:     127.0.0.1:65141 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:06:50] 2026-11-17 21:06:50,634 | INFO | agents.interview_agent.nodes | Skipped eval for thin/unanswered turn candidate=CAND-BB90FF6E question=q-2ad5d57222
[21:06:50] 2026-11-17 21:06:50,685 | INFO | interview.latency | {"event":"interview_latency","turn_id":"9a6340e0f8f5418186e705a2e2fde39e","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"answer","elapsed_ms":68.905,"metrics":{"redis_enqueue_ms":0.452,"langgraph_ms":18.66,"database_save_ms":38.015,"answer_api_ms":67.033},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_
[21:06:50] INFO:     127.0.0.1:58206 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/answer HTTP/1.1" 200 OK
[21:06:50] INFO:     127.0.0.1:60777 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/speak-stream HTTP/1.1" 200 OK
[21:06:53] INFO:     127.0.0.1:50133 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:06:55] 2026-11-17 21:06:54,543 | INFO | agents.interview_agent.streaming_tts | TTS stream done voice=en-IN-PrabhatIndicNeural bytes=240192 ttfa_ms=2241.3 total_ms=3725
[21:06:58] INFO:     127.0.0.1:53593 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:06:59] E0000 00:00:1794929818.407589   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T15:44:58.367871883+00:00
[21:06:59] === Source Location Trace: === 
[21:06:59] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[21:07:03] INFO:     127.0.0.1:63019 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:07:07] INFO:     127.0.0.1:51165 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:07:09] 2026-11-17 21:07:08,768 | INFO | interview.latency | {"event":"interview_latency","turn_id":"9a6340e0f8f5418186e705a2e2fde39e","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"client_turn_complete","elapsed_ms":0.091,"metrics":{"audio_input_sample_rate":48000.0,"silence_wait_ms":2531.0,"answer_recorded_ms":26979.0,"audio_upload_ms":5542.8,"transcribe_request_ms":5542.8,"stt_mode_effect
[21:07:09] INFO:     127.0.0.1:63493 - "WebSocket /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/stt-stream?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMDFhM2JhOC1jYmNlLTRmMzktYjA2Ni1lMmJhNTJjZWU1NWMiLCJ0eXAiOiJjYW5kaWRhdGUiLCJpYXQiOjE3OTQ5Mjk1NjgsImV4cCI6MTc5NDk3Mjc2OCwic2Vzc2lvbl9pZCI6IjM4NjRkMzNlLWZjMWUtNGQ2OC04NDE2LWQ3MmQwYzYwY2I0ZCIsInJyX2NhbmRpZGF0ZV9pZCI6IkNBTkQtQkI5ME
[21:07:09] INFO:     connection open
[21:07:09] INFO:     127.0.0.1:63491 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/latency-beacon HTTP/1.1" 200 OK
[21:07:09] 2026-11-17 21:07:08,792 | INFO | api.routes.candidate_interview_stt_ws | streaming_stt_turn_start session=3864d33e-fc1e-4d68-8416-d72d0c60cb4d question=q-1c58fce507
[21:07:09] INFO:     127.0.0.1:61427 - "GET /proctoring/pcm-worklet.js HTTP/1.1" 404 Not Found
[21:07:09] 2026-11-17 21:07:09,028 | INFO | api.routes.candidate_interview_stt_ws | streaming_stt_socket_closed session=3864d33e-fc1e-4d68-8416-d72d0c60cb4d started=True frames=0 bytes=0
[21:07:09] INFO:     connection closed
[21:07:12] INFO:     127.0.0.1:64778 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:07:13] 2026-11-17 21:07:13,168 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:07:13] 2026-11-17 21:07:13,174 | INFO | interview.latency | {"event":"interview_latency","turn_id":"d3e86c97597b4206bf07e8c194a73fe4","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":1023.435,"metrics":{"audio_receive_ms":0.044,"audio_bytes":48494,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databas
[21:07:13] INFO:     127.0.0.1:58715 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:07:16] 2026-11-17 21:07:16,840 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:07:16] 2026-11-17 21:07:16,843 | INFO | interview.latency | {"event":"interview_latency","turn_id":"e61699417c024ce5a50ac87bb4451456","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":1522.615,"metrics":{"audio_receive_ms":0.069,"audio_bytes":97808,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databas
[21:07:16] INFO:     127.0.0.1:51076 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:07:18] INFO:     127.0.0.1:65145 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:07:21] 2026-11-17 21:07:20,591 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:07:21] 2026-11-17 21:07:20,592 | INFO | interview.latency | {"event":"interview_latency","turn_id":"a7fdfa2c786d413a9f1c0cd934c8d549","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":2425.177,"metrics":{"audio_receive_ms":0.083,"audio_bytes":147122,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:07:21] INFO:     127.0.0.1:63433 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:07:23] INFO:     127.0.0.1:50947 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:07:24] 2026-11-17 21:07:23,758 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:07:24] 2026-11-17 21:07:23,758 | INFO | interview.latency | {"event":"interview_latency","turn_id":"43964af7805a4baf8e391e1f23b1e1a4","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":2705.037,"metrics":{"audio_receive_ms":0.109,"audio_bytes":196436,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:07:24] INFO:     127.0.0.1:62095 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:07:27] 2026-11-17 21:07:27,232 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:07:27] 2026-11-17 21:07:27,232 | INFO | interview.latency | {"event":"interview_latency","turn_id":"3acff04c4d884df687362a07ce878aa6","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":3186.424,"metrics":{"audio_receive_ms":0.121,"audio_bytes":245750,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:07:27] INFO:     127.0.0.1:52552 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:07:28] INFO:     127.0.0.1:61333 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:07:32] INFO:     127.0.0.1:55148 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:07:34] 2026-11-17 21:07:34,357 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:07:34] 2026-11-17 21:07:34,374 | INFO | interview.latency | {"event":"interview_latency","turn_id":"1b8473f4f2e249338fea8882574496bb","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":4229.079,"metrics":{"audio_receive_ms":0.399,"audio_bytes":344378,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:07:34] INFO:     127.0.0.1:51700 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:07:37] INFO:     127.0.0.1:51690 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:07:42] 2026-11-17 21:07:41,358 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:07:42] 2026-11-17 21:07:41,358 | INFO | interview.latency | {"event":"interview_latency","turn_id":"e88fadeeeac3444799bdf37eb2fcb44b","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":5294.58,"metrics":{"audio_receive_ms":0.111,"audio_bytes":443006,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databas
[21:07:42] INFO:     127.0.0.1:51895 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:07:43] INFO:     127.0.0.1:50826 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:07:48] INFO:     127.0.0.1:64348 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:07:49] 2026-11-17 21:07:48,436 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:07:49] 2026-11-17 21:07:48,442 | INFO | interview.latency | {"event":"interview_latency","turn_id":"68e0b02ff3544d368e28fef678b51f75","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":6276.9,"metrics":{"audio_receive_ms":0.181,"audio_bytes":541634,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","database
[21:07:49] INFO:     127.0.0.1:56954 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:07:53] INFO:     127.0.0.1:49913 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:07:57] INFO:     127.0.0.1:60226 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:07:59] E0000 00:00:1794929878.426918   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T15:44:58.367871883+00:00
[21:07:59] === Source Location Trace: === 
[21:07:59] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[21:07:59] 2026-11-17 21:07:58,677 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:07:59] 2026-11-17 21:07:58,682 | INFO | interview.latency | {"event":"interview_latency","turn_id":"d1dd4c5baab64c71a2e16ae92b929e40","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":7610.832,"metrics":{"audio_receive_ms":0.232,"audio_bytes":673138,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:07:59] INFO:     127.0.0.1:53736 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:08:01] 2026-11-17 21:08:00,452 | INFO | agents.interview_agent.stt_service | Azure STT chunking 51.0s audio into 2 parts for complete transcript
[21:08:03] INFO:     127.0.0.1:61613 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:08:06] 2026-11-17 21:08:05,726 | INFO | agents.interview_agent.stt_service | Azure STT chunking 54.8s audio into 2 parts for complete transcript
[21:08:08] INFO:     127.0.0.1:57076 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:08:08] 2026-11-17 21:08:08,338 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:08:10] 2026-11-17 21:08:09,954 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:08:10] 2026-11-17 21:08:09,958 | INFO | interview.latency | {"event":"interview_latency","turn_id":"ed592a2b182447baaff5681224e33330","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":9769.377,"metrics":{"audio_receive_ms":0.316,"audio_bytes":822046,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:08:10] INFO:     127.0.0.1:63362 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:08:13] INFO:     127.0.0.1:51293 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:08:14] 2026-11-17 21:08:14,446 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:08:16] 2026-11-17 21:08:16,590 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:08:18] 2026-11-17 21:08:18,372 | INFO | agents.interview_agent.stt_corrector | STT resume corrections (1 tier=technical status=pending_llm): [{'from': 'any', 'to': 'AND', 'reason': 'fuzzy resume match (0.92)'}]
[21:08:18] 2026-11-17 21:08:18,498 | INFO | interview.latency | {"event":"interview_latency","turn_id":"30eb8310f3664ec7b30501b8c1d20a1b","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe","elapsed_ms":13062.49,"metrics":{"audio_receive_ms":0.258,"audio_bytes":883933,"database_save_ms":82.058},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms"],"events":["a
[21:08:18] INFO:     127.0.0.1:54207 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:08:18] INFO:     127.0.0.1:49302 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:08:20] 2026-11-17 21:08:18,949 | INFO | interview.latency | {"event":"interview_latency","turn_id":"30eb8310f3664ec7b30501b8c1d20a1b","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"answer","elapsed_ms":140.158,"metrics":{"redis_enqueue_ms":0.132,"langgraph_ms":53.836,"database_save_ms":77.996,"answer_api_ms":137.888},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_aud
[21:08:20] INFO:     127.0.0.1:57457 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/answer HTTP/1.1" 200 OK
[21:08:20] INFO:     127.0.0.1:53180 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/speak-stream HTTP/1.1" 200 OK
[21:08:23] 2026-11-17 21:08:22,278 | INFO | agents.interview_agent.streaming_tts | TTS stream done voice=en-IN-PrabhatIndicNeural bytes=247104 ttfa_ms=1841.6 total_ms=3208
[21:08:24] INFO:     127.0.0.1:56625 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:08:28] INFO:     127.0.0.1:49278 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:08:33] INFO:     127.0.0.1:56262 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:08:37] 2026-11-17 21:08:36,858 | INFO | interview.latency | {"event":"interview_latency","turn_id":"30eb8310f3664ec7b30501b8c1d20a1b","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"client_turn_complete","elapsed_ms":0.067,"metrics":{"audio_input_sample_rate":48000.0,"silence_wait_ms":2519.1,"answer_recorded_ms":54866.0,"audio_upload_ms":13482.2,"transcribe_request_ms":13482.2,"stt_mode_effe
[21:08:37] INFO:     127.0.0.1:56173 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/latency-beacon HTTP/1.1" 200 OK
[21:08:37] INFO:     127.0.0.1:56175 - "WebSocket /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/stt-stream?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMDFhM2JhOC1jYmNlLTRmMzktYjA2Ni1lMmJhNTJjZWU1NWMiLCJ0eXAiOiJjYW5kaWRhdGUiLCJpYXQiOjE3OTQ5Mjk1NjgsImV4cCI6MTc5NDk3Mjc2OCwic2Vzc2lvbl9pZCI6IjM4NjRkMzNlLWZjMWUtNGQ2OC04NDE2LWQ3MmQwYzYwY2I0ZCIsInJyX2NhbmRpZGF0ZV9pZCI6IkNBTkQtQkI5ME
[21:08:37] INFO:     connection open
[21:08:37] 2026-11-17 21:08:36,950 | INFO | api.routes.candidate_interview_stt_ws | streaming_stt_turn_start session=3864d33e-fc1e-4d68-8416-d72d0c60cb4d question=q-1be2df36f9
[21:08:37] INFO:     127.0.0.1:54276 - "GET /proctoring/pcm-worklet.js HTTP/1.1" 404 Not Found
[21:08:37] 2026-11-17 21:08:37,085 | INFO | api.routes.candidate_interview_stt_ws | streaming_stt_socket_closed session=3864d33e-fc1e-4d68-8416-d72d0c60cb4d started=True frames=0 bytes=0
[21:08:37] INFO:     connection closed
[21:08:38] INFO:     127.0.0.1:56449 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:08:41] 2026-11-17 21:08:41,490 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:08:41] 2026-11-17 21:08:41,493 | INFO | interview.latency | {"event":"interview_latency","turn_id":"8eb32a0f74534750a4eff1137495273e","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":1049.085,"metrics":{"audio_receive_ms":0.06,"audio_bytes":48494},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms"],"events":["audio_reached_fastapi
[21:08:41] INFO:     127.0.0.1:52648 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 503 Service Unavailable
[21:08:43] INFO:     127.0.0.1:64451 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:08:46] 2026-11-17 21:08:45,157 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:08:46] 2026-11-17 21:08:45,158 | INFO | interview.latency | {"event":"interview_latency","turn_id":"34b35dfd70ae48c58e2a8be620d51c41","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":1678.13,"metrics":{"audio_receive_ms":0.056,"audio_bytes":98774,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","database
[21:08:46] INFO:     127.0.0.1:57547 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:08:49] INFO:     127.0.0.1:59122 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:08:49] 2026-11-17 21:08:48,618 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:08:49] 2026-11-17 21:08:48,623 | INFO | interview.latency | {"event":"interview_latency","turn_id":"58860085e46d449f9db348a293f1f107","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":2155.389,"metrics":{"audio_receive_ms":0.142,"audio_bytes":148088,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:08:49] INFO:     127.0.0.1:63379 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:08:52] 2026-11-17 21:08:52,024 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:08:52] 2026-11-17 21:08:52,027 | INFO | interview.latency | {"event":"interview_latency","turn_id":"79202557d1084a22907523f2f4dc364d","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":2584.27,"metrics":{"audio_receive_ms":0.092,"audio_bytes":197402,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databas
[21:08:52] INFO:     127.0.0.1:58924 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:08:53] INFO:     127.0.0.1:53154 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:08:55] 2026-11-17 21:08:55,408 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:08:55] 2026-11-17 21:08:55,408 | INFO | interview.latency | {"event":"interview_latency","turn_id":"706c7d25bef04f4cba79a727ae018ed7","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":3124.171,"metrics":{"audio_receive_ms":0.128,"audio_bytes":246716,"database_save_ms":null},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms","databa
[21:08:56] INFO:     127.0.0.1:49280 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:08:58] INFO:     127.0.0.1:61352 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:08:58] E0000 00:00:1794929938.438185   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T15:44:58.367871883+00:00
[21:08:58] === Source Location Trace: === 
[21:08:58] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[21:08:59] 2026-11-17 21:08:59,608 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:09:00] 2026-11-17 21:08:59,894 | INFO | interview.latency | {"event":"interview_latency","turn_id":"bf11ac9f33204e53ae0fc9eba3a72c04","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe","elapsed_ms":5029.847,"metrics":{"audio_receive_ms":0.11,"audio_bytes":252527,"database_save_ms":99.93},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms"],"events":["aud
[21:09:00] INFO:     127.0.0.1:57212 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 200 OK
[21:09:00] 2026-11-17 21:09:00,148 | INFO | agents.interview_agent.nodes | Skipped eval for thin/unanswered turn candidate=CAND-BB90FF6E question=q-1be2df36f9
[21:09:00] 2026-11-17 21:09:00,208 | INFO | interview.latency | {"event":"interview_latency","turn_id":"bf11ac9f33204e53ae0fc9eba3a72c04","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"answer","elapsed_ms":74.484,"metrics":{"redis_enqueue_ms":0.407,"langgraph_ms":17.454,"database_save_ms":46.382,"answer_api_ms":72.603},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio
[21:09:00] INFO:     127.0.0.1:64799 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/answer HTTP/1.1" 200 OK
[21:09:00] INFO:     127.0.0.1:63841 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/speak-stream HTTP/1.1" 200 OK
[21:09:03] INFO:     127.0.0.1:57978 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:09:03] 2026-11-17 21:09:03,605 | INFO | agents.interview_agent.streaming_tts | TTS stream done voice=en-IN-PrabhatIndicNeural bytes=264960 ttfa_ms=1785.1 total_ms=3332
[21:09:09] INFO:     127.0.0.1:64398 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:09:14] INFO:     127.0.0.1:52245 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:09:19] INFO:     127.0.0.1:51714 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:09:19] 2026-11-17 21:09:19,172 | INFO | interview.latency | {"event":"interview_latency","turn_id":"bf11ac9f33204e53ae0fc9eba3a72c04","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"client_turn_complete","elapsed_ms":0.077,"metrics":{"audio_input_sample_rate":48000.0,"silence_wait_ms":2518.0,"answer_recorded_ms":15708.0,"audio_upload_ms":5491.5,"transcribe_request_ms":5491.5,"stt_mode_effect
[21:09:19] INFO:     127.0.0.1:62469 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/latency-beacon HTTP/1.1" 200 OK
[21:09:19] INFO:     127.0.0.1:57049 - "WebSocket /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/stt-stream?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMDFhM2JhOC1jYmNlLTRmMzktYjA2Ni1lMmJhNTJjZWU1NWMiLCJ0eXAiOiJjYW5kaWRhdGUiLCJpYXQiOjE3OTQ5Mjk1NjgsImV4cCI6MTc5NDk3Mjc2OCwic2Vzc2lvbl9pZCI6IjM4NjRkMzNlLWZjMWUtNGQ2OC04NDE2LWQ3MmQwYzYwY2I0ZCIsInJyX2NhbmRpZGF0ZV9pZCI6IkNBTkQtQkI5ME
[21:09:19] INFO:     connection open
[21:09:19] 2026-11-17 21:09:19,268 | INFO | api.routes.candidate_interview_stt_ws | streaming_stt_turn_start session=3864d33e-fc1e-4d68-8416-d72d0c60cb4d question=q-a17aea7bf3
[21:09:19] INFO:     127.0.0.1:65297 - "GET /proctoring/pcm-worklet.js HTTP/1.1" 404 Not Found
[21:09:19] 2026-11-17 21:09:19,390 | INFO | api.routes.candidate_interview_stt_ws | streaming_stt_socket_closed session=3864d33e-fc1e-4d68-8416-d72d0c60cb4d started=True frames=0 bytes=0
[21:09:19] INFO:     connection closed
[21:09:23] INFO:     127.0.0.1:57197 - "POST /api/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/recording/chunks HTTP/1.1" 200 OK
[21:09:23] 2026-11-17 21:09:23,569 | INFO | httpx | HTTP Request: POST https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-IN&format=detailed "HTTP/1.1 200 OK"
[21:09:23] 2026-11-17 21:09:23,571 | INFO | interview.latency | {"event":"interview_latency","turn_id":"a5aeab12234e4d30b25fc88485a090e3","session_id":"3864d33e-fc1e-4d68-8416-d72d0c60cb4d","phase":"transcribe_partial","elapsed_ms":1099.23,"metrics":{"audio_receive_ms":0.072,"audio_bytes":48494},"unavailable_metrics":["llm_time_to_first_token_ms","tts_time_to_first_audio_ms"],"events":["audio_reached_fastapi
[21:09:23] INFO:     127.0.0.1:49802 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/ai/transcribe HTTP/1.1" 503 Service Unavailable
[21:09:27] INFO:     connection closed
[21:09:28] INFO:     127.0.0.1:61335 - "GET /api/auth/me HTTP/1.1" 200 OK
[21:09:28] INFO:     127.0.0.1:58447 - "GET /api/departments HTTP/1.1" 200 OK
[21:09:28] INFO:     127.0.0.1:61341 - "GET /api/jobs HTTP/1.1" 200 OK
[21:09:28] INFO:     127.0.0.1:61340 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[21:09:28] INFO:     127.0.0.1:61339 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[21:09:30] 2026-11-17 21:09:30,122 | INFO | httpx | HTTP Request: POST https://interview-openai-foundr-resource.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-10-21 "HTTP/1.1 200 OK"
[21:09:31] INFO:     127.0.0.1:58878 - "POST /api/interview/room/sessions/3864d33e-fc1e-4d68-8416-d72d0c60cb4d/leave HTTP/1.1" 200 OK
[21:09:33] INFO:     127.0.0.1:57845 - "GET /api/auth/me HTTP/1.1" 200 OK
[21:09:33] INFO:     127.0.0.1:57844 - "GET /api/interview/join/puDzb0azEZ8CCSO7T4K8EbPhi5XTOLfhZNvQ330uHu6v-eYM6lMP7WOOnA7jLAJl HTTP/1.1" 409 Conflict
[21:09:33] INFO:     127.0.0.1:57849 - "GET /api/auth/me HTTP/1.1" 200 OK
[21:09:33] INFO:     127.0.0.1:57851 - "GET /api/interview/join/puDzb0azEZ8CCSO7T4K8EbPhi5XTOLfhZNvQ330uHu6v-eYM6lMP7WOOnA7jLAJl HTTP/1.1" 409 Conflict
[21:09:33] INFO:     127.0.0.1:57853 - "GET /api/companies HTTP/1.1" 200 OK
[21:09:33] INFO:     127.0.0.1:65080 - "GET /api/settings HTTP/1.1" 200 OK
[21:09:33] INFO:     127.0.0.1:65089 - "GET /api/departments HTTP/1.1" 200 OK
[21:09:35] INFO:     127.0.0.1:65087 - "GET /api/hr/dashboard/stats HTTP/1.1" 200 OK
[21:09:35] INFO:     127.0.0.1:65088 - "GET /api/jobs HTTP/1.1" 200 OK
[21:09:35] INFO:     127.0.0.1:65090 - "GET /api/hr/audit-logs?limit=100&company_id=2 HTTP/1.1" 200 OK
[21:09:35] INFO:     127.0.0.1:65086 - "GET /api/hr/candidates?status=all HTTP/1.1" 200 OK
[21:09:59] E0000 00:00:1794929998.441454   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T15:44:58.367871883+00:00
[21:09:59] === Source Location Trace: === 
[21:09:59] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[21:10:59] E0000 00:00:1794930058.448254   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T15:44:58.367871883+00:00
[21:10:59] === Source Location Trace: === 
[21:10:59] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[21:11:59] E0000 00:00:1794930118.461229   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T15:44:58.367871883+00:00
[21:11:59] === Source Location Trace: === 
[21:11:59] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[21:12:20] INFO:     127.0.0.1:55593 - "GET /proctoring/pcm-worklet.js HTTP/1.1" 404 Not Found
[21:12:58] E0000 00:00:1794930178.465737   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T15:44:58.367871883+00:00
[21:12:58] === Source Location Trace: === 
[21:12:58] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
[21:13:58] E0000 00:00:1794930238.479200   23948 portable_clearcut_uploader.cc:90] Failed to send to clearcut: FAILED_PRECONDITION: Not valid for uploading until: 2026-11-17T15:44:58.367871883+00:00
[21:13:58] === Source Location Trace: === 
[21:13:58] wireless/android/play/playlog/cplusplus/portable_clearcut_uploader.cc:180
