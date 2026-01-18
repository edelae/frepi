# Frepi Agent - GCP Deployment Guide

## Step 1: Create GCP Project (if needed)

1. Go to https://console.cloud.google.com
2. Click "Select a project" → "New Project"
3. Name: `frepi-agent`
4. Click "Create"

## Step 2: Create VM Instance

### Option A: Using GCP Console (Recommended)

1. Go to **Compute Engine** → **VM instances**
2. Click **Create Instance**
3. Configure:
   - **Name:** `frepi-agent-vm`
   - **Region:** `southamerica-east1` (São Paulo)
   - **Zone:** `southamerica-east1-a`
   - **Machine type:** `e2-micro` (free tier) or `e2-small` ($6/month)
   - **Boot disk:**
     - Ubuntu 22.04 LTS
     - 20 GB Standard persistent disk
   - **Firewall:** Check "Allow HTTP traffic"
4. Click **Create**

### Option B: Using gcloud CLI

```bash
gcloud compute instances create frepi-agent-vm \
    --project=frepi-agent \
    --zone=southamerica-east1-a \
    --machine-type=e2-micro \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=20GB \
    --tags=http-server
```

## Step 3: Connect to VM

```bash
gcloud compute ssh frepi-agent-vm --zone=southamerica-east1-a
```

Or use the **SSH** button in the GCP Console.

## Step 4: Upload Files

From your local machine:

```bash
# Create a zip of the project
cd /path/to/frepi-agent
zip -r frepi-agent.zip frepi_agent scripts deploy requirements.txt

# Upload to VM
gcloud compute scp frepi-agent.zip frepi-agent-vm:~ --zone=southamerica-east1-a
```

## Step 5: Install on VM

On the VM:

```bash
# Unzip
unzip frepi-agent.zip
cd frepi-agent

# Run setup script
chmod +x deploy/setup.sh
./deploy/setup.sh
```

## Step 6: Configure Environment

Edit the `.env` file with your credentials:

```bash
sudo nano /opt/frepi-agent/.env
```

Add your values:
```
OPENAI_API_KEY=sk-proj-...
SUPABASE_URL=https://oknotufkobuwpmtyslma.supabase.co
SUPABASE_KEY=eyJ...
TELEGRAM_BOT_TOKEN=7725859508:AAGQ-...
```

## Step 7: Start the Service

```bash
# Start the bot
sudo systemctl start frepi-agent

# Check status
sudo systemctl status frepi-agent

# View logs
sudo journalctl -u frepi-agent -f
```

## Useful Commands

```bash
# Stop the bot
sudo systemctl stop frepi-agent

# Restart the bot
sudo systemctl restart frepi-agent

# View recent logs
sudo journalctl -u frepi-agent --since "1 hour ago"

# Test connection manually
cd /opt/frepi-agent
source venv/bin/activate
python -m frepi_agent.main test
```

## Estimated Costs

| Resource | Cost |
|----------|------|
| e2-micro VM | $0 (free tier) or ~$6/month |
| 20GB disk | ~$0.80/month |
| Network egress | ~$0.12/GB (minimal for text) |
| **Total** | **~$0-10/month** |

## Troubleshooting

### Bot not responding
```bash
# Check if service is running
sudo systemctl status frepi-agent

# Check logs for errors
sudo journalctl -u frepi-agent -n 50
```

### Token conflict
If you see "Conflict: terminated by other getUpdates request":
- Make sure no other service is using the same Telegram bot token
- Stop any n8n workflows using this bot
- Or create a new bot with @BotFather

### Out of memory
If using e2-micro and running out of memory:
```bash
# Upgrade to e2-small
gcloud compute instances stop frepi-agent-vm
gcloud compute instances set-machine-type frepi-agent-vm --machine-type=e2-small
gcloud compute instances start frepi-agent-vm
```
