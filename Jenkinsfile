// ============================================================
//  Jenkinsfile  —  DevOps Health Monitor CI/CD Pipeline
//  Stages: Checkout → Lint → Test → Build → Deploy → Cleanup
// ============================================================

pipeline {

    agent any   // Run on any available Jenkins agent

    // ── Trigger: every 30 minutes + on SCM push ──────────────
    triggers {
        pollSCM('H/30 * * * *')
    }

    // ── Pipeline-wide environment ────────────────────────────
    environment {
        IMAGE_NAME   = 'devops-health-monitor'
        IMAGE_TAG    = "${env.BUILD_NUMBER}"
        REPORTS_DIR  = "${env.WORKSPACE}/reports"
        THRESHOLD_CPU  = '80'
        THRESHOLD_MEM  = '85'
        THRESHOLD_DISK = '90'
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    // ════════════════════════════════════════════════════════
    //  S T A G E S
    // ════════════════════════════════════════════════════════
    stages {

        // ── 1. Checkout ──────────────────────────────────────
        stage('Checkout') {
            steps {
                echo "Branch: ${env.BRANCH_NAME ?: 'N/A'}"
                echo "Build:  #${env.BUILD_NUMBER}"
                checkout scm
                sh 'git log --oneline -5 || true'
            }
        }

        // ── 2. Lint ──────────────────────────────────────────
        stage('Lint') {
            steps {
                echo 'Checking shell scripts …'
                sh '''
                    if command -v shellcheck &>/dev/null; then
                        shellcheck scripts/*.sh
                        echo "shellcheck: OK"
                    else
                        echo "shellcheck not installed — skipping"
                    fi
                '''
                echo 'Checking Python syntax …'
                sh 'python3 -m py_compile app/monitor.py && echo "Syntax: OK"'
            }
        }

        // ── 3. Unit Tests ────────────────────────────────────
        stage('Test') {
            steps {
                echo 'Running unit tests …'
                sh '''
                    python3 -m pytest tests/ \
                        -v \
                        --tb=short \
                        --junit-xml=reports/junit.xml \
                        2>&1 | tee reports/test_output.log
                '''
            }
            post {
                always {
                    // Publish JUnit results if the plugin is installed
                    script {
                        if (fileExists('reports/junit.xml')) {
                            junit 'reports/junit.xml'
                        }
                    }
                }
            }
        }

        // ── 4. Docker Build ──────────────────────────────────
        stage('Docker Build') {
            steps {
                echo "Building Docker image ${env.IMAGE_NAME}:${env.IMAGE_TAG} …"
                sh '''
                    docker build \
                        -f docker/Dockerfile \
                        -t ${IMAGE_NAME}:${IMAGE_TAG} \
                        -t ${IMAGE_NAME}:latest \
                        --label "jenkins.build=${BUILD_NUMBER}" \
                        --label "jenkins.job=${JOB_NAME}" \
                        .
                    docker images ${IMAGE_NAME}
                '''
            }
        }

        // ── 5. Health-check Run ──────────────────────────────
        stage('Health Check') {
            steps {
                echo 'Running health monitor inside Docker …'
                sh '''
                    mkdir -p ${REPORTS_DIR}
                    docker run --rm \
                        -v ${REPORTS_DIR}:/app/reports \
                        -e THRESHOLD_CPU=${THRESHOLD_CPU}   \
                        -e THRESHOLD_MEM=${THRESHOLD_MEM}   \
                        -e THRESHOLD_DISK=${THRESHOLD_DISK} \
                        ${IMAGE_NAME}:${IMAGE_TAG} \
                    || EXIT=$?; echo "Monitor exit code: ${EXIT:-0}"
                '''
                echo 'Latest report:'
                sh 'ls -lh ${REPORTS_DIR}/*.json 2>/dev/null | tail -3 || true'
            }
        }

        // ── 6. Archive artefacts ─────────────────────────────
        stage('Archive') {
            steps {
                archiveArtifacts artifacts: 'reports/*.json,reports/*.log',
                                 allowEmptyArchive: true
                echo 'Reports archived as Jenkins build artefacts.'
            }
        }

        // ── 7. Cleanup ───────────────────────────────────────
        stage('Cleanup') {
            steps {
                echo 'Cleaning old reports and Docker artefacts …'
                sh 'bash scripts/cleanup.sh || true'
            }
        }

    } // end stages

    // ════════════════════════════════════════════════════════
    //  P O S T   A C T I O N S
    // ════════════════════════════════════════════════════════
    post {
        success {
            echo "✅ Pipeline PASSED — Build #${env.BUILD_NUMBER}"
        }
        failure {
            echo "❌ Pipeline FAILED — Build #${env.BUILD_NUMBER}"
        }
        unstable {
            echo "⚠️  Pipeline UNSTABLE — check test results"
        }
        always {
            cleanWs(cleanWhenSuccess: false)   // keep workspace on failure for debug
        }
    }

}
