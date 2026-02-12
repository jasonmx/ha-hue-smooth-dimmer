#!/bin/bash

# Exit if a ssh command fails
set -e

echo "Stopping HA..."
ssh rpi "docker stop homeassistant"

echo "Deploying custom component..."
rsync -av --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  custom_components/hue_dimmer \
  rpi:/home/pi/homeassistant/homeassistant_config/custom_components/

echo "Starting HA..."
ssh rpi "docker start homeassistant"

ssh rpi "cd /home/pi/homeassistant && docker compose ps --format 'table {{.Name}}\t{{.State}}\t{{.Status}}' homeassistant"
