# AWS Production Deployment Guide

This guide outlines the production deployment workflow for the AI Quiz Generator. In production, we separate the application servers (EC2) from the database layers (AWS RDS) to ensure durability, high availability, and routine automated backups.

---

## 1. Provision AWS Resources

### Step 1.1: Launch the EC2 Instance
1. Log in to your AWS Management Console and navigate to **EC2**.
2. Click **Launch Instance** and configure:
   * **Name**: `ai-quiz-generator-app`
   * **OS (AMI)**: `Ubuntu Server 22.04 LTS` (64-bit x86)
   * **Instance Type**: `t3.small` (2 vCPUs, 2 GiB Memory)
   * **Key Pair**: Choose an existing key pair or create a new one.
3. Under **Network settings**, configure the Security Group:
   * Create a new security group `quiz-app-sg`.
   * Add the following **Inbound Rules**:
     * **SSH** (Port 22) -> Source: `My IP` (or your administration subnet)
     * **Custom TCP** (Port 5000) -> Source: `Anywhere-IPv4` (`0.0.0.0/0`) *— for backend API access*
     * **Custom TCP** (Port 8501) -> Source: `Anywhere-IPv4` (`0.0.0.0/0`) *— for Streamlit frontend*
   * *Note: Port 5432 should **NOT** be open to the internet on this instance.*

### Step 1.2: Provision the AWS RDS PostgreSQL Instance
1. Navigate to **RDS** in the AWS Console and click **Create database**.
2. Select **Standard create** -> **PostgreSQL**.
3. Choose **Engine Version**: `PostgreSQL 16` (matching local Docker configuration).
4. Under **Templates**, select **Free Tier** (or **Dev/Test** for staging/production).
5. Configure DB details:
   * **DB instance identifier**: `quiz-postgres-db`
   * **Master username**: `quizapp`
   * **Master password**: *Choose a secure password*
   * **Instance configuration**: `db.t3.micro` (or `db.t3.small`)
6. Under **Connectivity**:
   * **Public access**: Select **No** (crucial for security).
   * **VPC security group**: Choose **Create new** and name it `quiz-db-sg`.
7. Click **Create database**.
8. Once the database status changes to **Available**, click on `quiz-postgres-db` and copy the **Endpoint** address (e.g. `quiz-postgres-db.xxxx.us-east-1.rds.amazonaws.com`).
9. Under the database **Connectivity & security** tab, click the `quiz-db-sg` security group:
   * Edit **Inbound Rules** to allow:
     * **PostgreSQL** (Port 5432) -> Source: Custom -> Type the ID of the EC2 security group `quiz-app-sg`.
     * **Delete** any default inbound rule allowing port 5432 from `0.0.0.0/0`.

---

## 2. Set Up the EC2 Instance

### Step 2.1: Connect via SSH
Open your terminal and connect to the newly created EC2 instance:
```bash
ssh -i /path/to/key.pem ubuntu@<ec2-public-ip>
```

### Step 2.2: Install Docker and Docker Compose
Run the following script to install Docker and the Docker Compose plugin on Ubuntu:
```bash
# Update package index
sudo apt-get update -y

# Install prerequisite packages
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker’s official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up the stable repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine & Compose
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify installation
sudo docker --version
sudo docker compose version

# Add the current user to the docker group so you don't need 'sudo' prefix
sudo usermod -aG docker $USER
newgrp docker
```

---

## 3. Clone and Configure the Application

### Step 3.1: Clone the Repository
```bash
git clone https://github.com/your-username/AI-Quiz-Generator.git
cd AI-Quiz-Generator
```

### Step 3.2: Create the `.env` Configuration File
Create a new file named `.env` in the root of the project directory. This file is excluded from source control:
```bash
nano .env
```

Paste and configure the following parameters:
```ini
# Flask Setup
FLASK_APP=app.py
FLASK_ENV=production

# Groq API Configuration
GROQ_API_KEY=your_groq_api_key_here
GROQ_CHAT_MODEL=llama-3.1-8b-instant
GROQ_EVAL_MODEL=llama-3.1-8b-instant
GROQ_WHISPER_MODEL=whisper-large-v3

# File Directory Layout
UPLOAD_FOLDER=uploads
TEMP_FOLDER=temp
OUTPUT_FOLDER=outputs
LOG_FOLDER=logs

# Security Credentials
# Generate a secure JWT secret using: python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=paste_secure_random_key_here
JWT_ACCESS_EXPIRY_MINUTES=60
JWT_REFRESH_EXPIRY_DAYS=30

# CORS & Frontend Origins
# Set this to the public URL/domain of your Streamlit frontend
ALLOWED_ORIGINS=http://<ec2-public-ip>:8501

# Database Configuration (AWS RDS PostgreSQL Endpoint)
POSTGRES_USER=quizapp
POSTGRES_PASSWORD=your_rds_secure_password
POSTGRES_DB=ai_quiz_generator
DATABASE_URL=postgresql://quizapp:your_rds_secure_password@quiz-postgres-db.xxxx.us-east-1.rds.amazonaws.com:5432/ai_quiz_generator
```

Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

---

## 4. Run the Production Containers

Start the services using the base Compose file joined with the production override file:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### What happens under the hood?
1. The `db` service definition is disabled (scaled to 0), preventing a PostgreSQL container from starting on the EC2 host.
2. The `backend` and `frontend` images are built.
3. The backend container boots up and triggers `deploy/entrypoint.sh`.
4. The entrypoint script runs `flask db upgrade`, applying all Alembic database migrations directly against the secure AWS RDS instance.
5. Gunicorn starts the Flask application on port `5000`.

---

## 5. Verify the Deployment

1. **Verify Backend Health Status**:
   ```bash
   curl http://localhost:5000/health
   ```
   You should receive a successful `200 OK` JSON response:
   ```json
   {"status":"healthy","version":"2.0.0","uptime":"..."}
   ```

2. **Test stream logs (optional)**:
   ```bash
   docker compose logs -f backend
   ```

3. **Access Streamlit Frontend**:
   Open a web browser and navigate to:
   ```
   http://<ec2-public-ip>:8501
   ```
   * Register a new account on the **Sign Up** tab.
   * Log in to access the system and run a test quiz generation.

---

## 6. Updating the Application

When code is pushed to your remote repository, pull the updates and recreate the containers:
```bash
# Pull latest code
git pull origin main

# Rebuild and run containers (zero downtime migration checks)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## 7. Production Security Checklist

* [ ] **Restrict EC2 Security Group Access**: Limit inbound port 22 (SSH) strictly to known administrator IP addresses.
* [ ] **Lock Down .env File Permissions**: Ensure the `.env` configuration file cannot be read by other Linux users:
  ```bash
  chmod 600 .env
  ```
* [ ] **CORS Settings**: Do not use `ALLOWED_ORIGINS=*` in production. Restrict it to the specific domains or public IPs of your application.
* [ ] **Rotate JWT Keys**: Regenerate the `JWT_SECRET_KEY` periodically.
* [ ] **Enable RDS Automated Backups**: Ensure automated backups are configured in your RDS settings (retained for at least 7–14 days).
* [ ] **Enable RDS Deletion Protection**: Turn on deletion protection in the RDS console to prevent accidental database deletion.
