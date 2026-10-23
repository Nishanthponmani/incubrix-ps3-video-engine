# Build plan

## Milestone 1 — Minimal renderer
- [x] Project scaffold
- [x] FFmpeg renderer for one video + one narration file
- [x] Aspect ratio normalization
- [x] Basic validation tests
- [ ] Verify Python and FFmpeg on the user's machine
- [ ] Render a real sample and inspect output

## Milestone 2 — API and job tracking
- [ ] Request validation
- [ ] `POST /api/v1/broll/jobs` returns HTTP 202 and a job ID
- [ ] Job status and progress
- [ ] Idempotency key
- [ ] Structured errors and correlation IDs

## Milestone 3 — Actual script/audio pipeline
- [ ] Text-to-speech
- [ ] Audio transcription with timestamps
- [ ] Scene planning
- [ ] Licensed footage adapter and fallback
- [ ] Captions, timeline and manifest
