pipeline {

    agent any

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

    stages {

        stage('Checkout') {
            steps {
                echo "Branch: ${env.BRANCH_NAME ?: 'N/A'}"
                echo "Build:  #${env.BUILD_NUMBER}"
                checkout scm
                sh 'git log --oneline -5 || true'
            }
        }

        stage('Lint') {
            steps {
                echo 'Checking shell scripts ...'
                sh '''
                    if command -v shellcheck > /dev/null 2>&1; then
                        shellcheck scripts/cleanup.sh && echo "shellcheck: OK"
                    else
                        echo "shellcheck not installed - skipping"
                    fi
                '''
                echo 'Checking Python syntax ...'
                sh 'python3 -m py_compile app/monitor.py && echo "Syntax: OK"'
            }
        }

        stage('Test') {
            steps {
                sh 'pip3 install pytest --break-system-packages -q 2>/dev/null || pip3 install pytest -q || true'
                sh '''
                    mkdir -p reports
                    if [ -f tests/test_monitor.py ]; then
                        python3 -m pytest tests/ -v --tb=short --junit-xml=reports/junit.xml 2>&1 | tee reports/test_output.log
                    else
                        echo "No tests found - skipping"
                        echo "<?xml version=1.0?><testsuites><testsuite name=empty tests=0/></testsuites>" > reports/junit.xml
                    fi
                '''
            }
            post {
                always {
                    script {
                        if (fileExists('reports/junit.xml')) {
                            try {
                                junit allowEmptyResults: true, testResults: 'reports/junit.xml'
                            } catch (err) {
                                echo "JUnit skipped: ${err.message}"
                            }
                        }
                    }
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    docker build \
                        -f docker/Dockerfile \
                        -t ${IMAGE_NAME}:${IMAGE_TAG} \
                        -t ${IMAGE_NAME}:latest \
                        .
                    docker images ${IMAGE_NAME}
                '''
            }
        }

        stage('Health Check') {
            steps {
                sh '''
                    mkdir -p ${REPORTS_DIR}
                    docker run --rm \
                        -v ${REPORTS_DIR}:/app/reports \
                        -e THRESHOLD_CPU=${THRESHOLD_CPU} \
                        -e THRESHOLD_MEM=${THRESHOLD_MEM} \
                        -e THRESHOLD_DISK=${THRESHOLD_DISK} \
                        ${IMAGE_NAME}:${IMAGE_TAG} || true
                '''
                sh 'ls -lh ${REPORTS_DIR}/*.json 2>/dev/null | tail -3 || echo "No reports yet"'
            }
        }

        stage('Archive') {
            steps {
                archiveArtifacts artifacts: 'reports/*.json,reports/*.log',
                                 allowEmptyArchive: true
            }
        }

        stage('Cleanup') {
            steps {
                sh 'bash scripts/cleanup.sh || true'
            }
        }

    }

    post {
        success {
            echo "Pipeline PASSED - Build #${env.BUILD_NUMBER}"
        }
        failure {
            echo "Pipeline FAILED - Build #${env.BUILD_NUMBER}"
        }
        always {
            deleteDir()
        }
    }

}
