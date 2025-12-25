"""
Backend API Testing for TTS Chunker App
Tests all API endpoints with proper error handling and reporting
"""

import requests
import time
import sys
from datetime import datetime

# Use the public endpoint
BASE_URL = "https://larynx-voice.preview.emergentagent.com"

class TTSChunkerAPITester:
    def __init__(self):
        self.base_url = BASE_URL
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.created_job_id = None
        
    def log_test(self, name, passed, message="", response_data=None):
        """Log test result"""
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            print(f"✅ PASS: {name}")
            if message:
                print(f"   {message}")
        else:
            print(f"❌ FAIL: {name}")
            print(f"   {message}")
        
        self.test_results.append({
            "test": name,
            "passed": passed,
            "message": message,
            "response": response_data
        })
        print()
    
    def test_health_check(self):
        """Test health check endpoint"""
        print("🔍 Testing Health Check...")
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    self.log_test(
                        "Health Check",
                        True,
                        f"Status: {response.status_code}, Service: {data.get('service')}"
                    )
                    return True
                else:
                    self.log_test(
                        "Health Check",
                        False,
                        f"Unexpected response: {data}"
                    )
                    return False
            else:
                self.log_test(
                    "Health Check",
                    False,
                    f"Expected 200, got {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.log_test("Health Check", False, f"Error: {str(e)}")
            return False
    
    def test_create_job(self):
        """Test creating a TTS job"""
        print("🔍 Testing Create Job (POST /api/jobs)...")
        
        # Create test text (500-1000 chars for faster testing)
        test_text = """
        This is a comprehensive test of the text-to-speech chunking system. 
        The system is designed to handle very long texts by breaking them into manageable chunks. 
        Each chunk is processed separately through the ElevenLabs API. 
        The resulting audio segments are then merged into a single MP3 file. 
        This approach allows for processing texts that would otherwise exceed API limits. 
        The chunking algorithm respects sentence boundaries to ensure natural speech flow. 
        Progress is tracked throughout the process so users can monitor the conversion. 
        When complete, users can download the final audio file. 
        This test uses a shorter sample to verify functionality without long wait times.
        The system handles various text formats and maintains audio quality throughout the process.
        """ * 2  # Repeat to get ~600 chars
        
        payload = {
            "name": f"Test Job {datetime.now().strftime('%H:%M:%S')}",
            "text": test_text.strip()
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/jobs",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                self.created_job_id = data.get("id")
                
                # Verify response structure
                required_fields = ["id", "name", "status", "progress", "chunk_count", "text_length"]
                missing_fields = [f for f in required_fields if f not in data]
                
                if missing_fields:
                    self.log_test(
                        "Create Job",
                        False,
                        f"Missing fields: {missing_fields}"
                    )
                    return False
                
                self.log_test(
                    "Create Job",
                    True,
                    f"Job ID: {self.created_job_id}, Status: {data.get('status')}, Chunks: {data.get('chunk_count')}, Text Length: {data.get('text_length')}",
                    data
                )
                return True
            else:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get("detail", error_msg)
                except:
                    pass
                
                self.log_test(
                    "Create Job",
                    False,
                    f"Expected 200, got {response.status_code}. Error: {error_msg}"
                )
                return False
                
        except Exception as e:
            self.log_test("Create Job", False, f"Error: {str(e)}")
            return False
    
    def test_list_jobs(self):
        """Test listing all jobs"""
        print("🔍 Testing List Jobs (GET /api/jobs)...")
        
        try:
            response = requests.get(f"{self.base_url}/api/jobs", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify response structure
                if "jobs" not in data or "total" not in data:
                    self.log_test(
                        "List Jobs",
                        False,
                        "Response missing 'jobs' or 'total' field"
                    )
                    return False
                
                jobs = data.get("jobs", [])
                total = data.get("total", 0)
                
                self.log_test(
                    "List Jobs",
                    True,
                    f"Found {len(jobs)} jobs (Total: {total})"
                )
                return True
            else:
                self.log_test(
                    "List Jobs",
                    False,
                    f"Expected 200, got {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.log_test("List Jobs", False, f"Error: {str(e)}")
            return False
    
    def test_get_job(self):
        """Test getting a specific job"""
        print("🔍 Testing Get Job (GET /api/jobs/{id})...")
        
        if not self.created_job_id:
            self.log_test(
                "Get Job",
                False,
                "No job ID available (create job test may have failed)"
            )
            return False
        
        try:
            response = requests.get(
                f"{self.base_url}/api/jobs/{self.created_job_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify response structure
                required_fields = ["id", "name", "status", "progress", "chunk_count"]
                missing_fields = [f for f in required_fields if f not in data]
                
                if missing_fields:
                    self.log_test(
                        "Get Job",
                        False,
                        f"Missing fields: {missing_fields}"
                    )
                    return False
                
                self.log_test(
                    "Get Job",
                    True,
                    f"Job ID: {data.get('id')}, Status: {data.get('status')}, Progress: {data.get('progress')}%"
                )
                return True
            else:
                self.log_test(
                    "Get Job",
                    False,
                    f"Expected 200, got {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.log_test("Get Job", False, f"Error: {str(e)}")
            return False
    
    def test_job_processing(self):
        """Test job processing by polling until completion or timeout"""
        print("🔍 Testing Job Processing (polling for completion)...")
        
        if not self.created_job_id:
            self.log_test(
                "Job Processing",
                False,
                "No job ID available"
            )
            return False
        
        max_wait_time = 60  # 60 seconds max wait
        poll_interval = 3  # Check every 3 seconds
        start_time = time.time()
        
        try:
            while time.time() - start_time < max_wait_time:
                response = requests.get(
                    f"{self.base_url}/api/jobs/{self.created_job_id}",
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")
                    progress = data.get("progress", 0)
                    
                    print(f"   Status: {status}, Progress: {progress}%")
                    
                    if status == "completed":
                        elapsed = time.time() - start_time
                        self.log_test(
                            "Job Processing",
                            True,
                            f"Job completed in {elapsed:.1f}s. Duration: {data.get('duration_seconds', 0):.2f}s"
                        )
                        return True
                    elif status == "failed":
                        error = data.get("error", "Unknown error")
                        self.log_test(
                            "Job Processing",
                            False,
                            f"Job failed: {error}"
                        )
                        return False
                    
                    # Still processing, wait and check again
                    time.sleep(poll_interval)
                else:
                    self.log_test(
                        "Job Processing",
                        False,
                        f"Error polling job: {response.status_code}"
                    )
                    return False
            
            # Timeout
            self.log_test(
                "Job Processing",
                False,
                f"Job did not complete within {max_wait_time}s (this may be expected for longer texts)"
            )
            return False
            
        except Exception as e:
            self.log_test("Job Processing", False, f"Error: {str(e)}")
            return False
    
    def test_download_audio(self):
        """Test downloading completed job audio"""
        print("🔍 Testing Download Audio (GET /api/jobs/{id}/download)...")
        
        if not self.created_job_id:
            self.log_test(
                "Download Audio",
                False,
                "No job ID available"
            )
            return False
        
        try:
            # First check if job is completed
            job_response = requests.get(
                f"{self.base_url}/api/jobs/{self.created_job_id}",
                timeout=10
            )
            
            if job_response.status_code != 200:
                self.log_test(
                    "Download Audio",
                    False,
                    "Could not fetch job status"
                )
                return False
            
            job_data = job_response.json()
            if job_data.get("status") != "completed":
                self.log_test(
                    "Download Audio",
                    False,
                    f"Job not completed (status: {job_data.get('status')}). Cannot test download."
                )
                return False
            
            # Try to download
            response = requests.get(
                f"{self.base_url}/api/jobs/{self.created_job_id}/download",
                timeout=30
            )
            
            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "")
                content_length = len(response.content)
                
                if "audio" in content_type or content_length > 0:
                    self.log_test(
                        "Download Audio",
                        True,
                        f"Downloaded {content_length} bytes, Content-Type: {content_type}"
                    )
                    return True
                else:
                    self.log_test(
                        "Download Audio",
                        False,
                        f"Invalid audio response: {content_type}, {content_length} bytes"
                    )
                    return False
            else:
                self.log_test(
                    "Download Audio",
                    False,
                    f"Expected 200, got {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.log_test("Download Audio", False, f"Error: {str(e)}")
            return False
    
    def test_delete_job(self):
        """Test deleting a job"""
        print("🔍 Testing Delete Job (DELETE /api/jobs/{id})...")
        
        if not self.created_job_id:
            self.log_test(
                "Delete Job",
                False,
                "No job ID available"
            )
            return False
        
        try:
            response = requests.delete(
                f"{self.base_url}/api/jobs/{self.created_job_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify job is deleted by trying to fetch it
                verify_response = requests.get(
                    f"{self.base_url}/api/jobs/{self.created_job_id}",
                    timeout=10
                )
                
                if verify_response.status_code == 404:
                    self.log_test(
                        "Delete Job",
                        True,
                        f"Job deleted successfully: {data.get('message', '')}"
                    )
                    return True
                else:
                    self.log_test(
                        "Delete Job",
                        False,
                        "Job still exists after deletion"
                    )
                    return False
            else:
                self.log_test(
                    "Delete Job",
                    False,
                    f"Expected 200, got {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.log_test("Delete Job", False, f"Error: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all backend API tests"""
        print("=" * 70)
        print("TTS CHUNKER BACKEND API TESTS")
        print(f"Base URL: {self.base_url}")
        print("=" * 70)
        print()
        
        # Run tests in order
        self.test_health_check()
        self.test_create_job()
        self.test_list_jobs()
        self.test_get_job()
        self.test_job_processing()
        self.test_download_audio()
        self.test_delete_job()
        
        # Print summary
        print("=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        print("=" * 70)
        
        return self.tests_passed == self.tests_run


def main():
    tester = TTSChunkerAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
