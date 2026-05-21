# Cookie Detect Docker Runbook

Minimal steps to run the project on EC2 with Docker.


## 1. SSH into EC2

Run this from your local computer:

```bash
ssh -i "cookie-banner-automation-key.pem" ubuntu@ec2-3-131-85-149.us-east-2.compute.amazonaws.com
```

## 2. GitHub Access
Check if the E2C instance already has an ssh key. Do 

```bash
cat ~/.ssh/id_ed25519.pub
```

If you get an error "no such file or directory," then do:

```bash
ssh-keygen -t ed25519 -C "cookie-detect-ec2-deploy-key"
cat ~/.ssh/id_ed25519.pub
```

Copy the printed public key.

In GitHub, go to:

```text
Repo → Settings → Deploy keys → Add deploy key
```

Add the public key and leave **Allow write access** unchecked.

## 3. Clone or update the repo

On the EC2 instance:

First check if the code is already cloned. If not, do:

```bash
cd ~

git clone git@github.com:MarcusBluestone/cookie_detection.git cookie_detect
cd cookie_detect
```

If the repo is already cloned:

```bash
cd ~/cookie_detect
git pull
```

## 4. Add API_KEYS

Ask Marcus Bluestone to pass the full `credentials` folder to the EC2 instance via SSH/SCP.

From your local computer, copy the folder to EC2. Replace `path_to_credentials_folder` with the local path to the `credentials` folder:

```bash
scp -i "cookie-banner-automation-key.pem" -r \
  path_to_credentials_folder \
  ubuntu@ec2-3-131-85-149.us-east-2.compute.amazonaws.com:~/cookie_detect/credentials
```

This copies the local folder you provide into `~/cookie_detect/credentials`. 


## 5. Install Docker on the E2C Instance
If docker isn't installed, run:
```bash
sudo apt update
sudo apt install -y docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
```

## 6. Build the Docker image

From `~/cookie_detect`:

```bash
docker build -t cookie-detect .
```

## 7. Run the scraper

```bash
mkdir -p ~/cookie_detect_outputs

docker run --rm \
  --env-file .env \
  -v ~/cookie_detect_outputs:/app/outputs \
  cookie-detect
```

Outputs will be saved on the EC2 instance at:

```text
~/cookie_detect_outputs
```

## 8. Copy outputs back to local

Run this from your *local* computer, not from inside SSH:

```bash
scp -i "./cookie-banner-automation-key.pem" -r \
  ubuntu@ec2-3-131-85-149.us-east-2.compute.amazonaws.com:~/cookie_detect_outputs \
  path_to_local_directory
```

Replace `path_to_local_directory` with the local folder where you want the outputs copied.

## Notes

This Docker setup does not use the proxy flow.

If the EC2 instance is refreshed, SSH into the new instance, clone the repo again, rebuild the Docker image, and rerun the container.