# API Test Scripts

These shell scripts are for WSL, Linux, or Git Bash style usage.

## Setup

1. Open [config.sh](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/test/config.sh)
2. Change `API_KEY` once

Important:
- For `.sh` scripts, use WSL/Linux style paths like `/mnt/c/Users/zoen/Downloads/video.mp4`
- If you are in Windows PowerShell, use the API guide examples instead of these `.sh` files
- Only `API_KEY` is shared now
- The sample file paths, URLs, and email are written directly inside each script

## Main scripts

- `./upload-local.sh`
- `./transcribe-gdrive.sh`
- `./transcribe-youtube.sh`
- `./list-videos.sh`
- `./get-video.sh <job_id>`
- `./retry-job.sh <job_id>`
- `./regenerate-summary.sh <job_id> ["instruction"]`
- `./chat.sh <job_id> ["question"]`
- `./chat-suggestions.sh <job_id>`
- `./chat-messages.sh <job_id>`
- `./download-source.sh <job_id> [output_path]`
- `./download-report.sh <job_id> [summary|transcript] [output_path]`
- `./email-report.sh <job_id> [summary|transcript] [recipient_email]`

## Example flow

```bash
cd /mnt/c/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/test
chmod +x ./*.sh
./upload-local.sh
./list-videos.sh
./get-video.sh JOB_ID
./download-report.sh JOB_ID summary ./summary-report.pdf
```
