"""
Unit tests for platform adapters (GitLab, GitHub, Harness)
"""
import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from k8s_validator.platforms.gitlab import GitLabAdapter
from k8s_validator.platforms.github import GitHubAdapter
from k8s_validator.platforms.harness import HarnessAdapter
from k8s_validator.platforms.detector import get_platform


# ============================================================================
# Platform Detector Tests
# ============================================================================

class TestPlatformDetector:
    """Test platform detection logic"""

    def test_detect_gitlab_ci(self, monkeypatch):
        """Test GitLab CI detection"""
        monkeypatch.setenv('GITLAB_CI', 'true')
        monkeypatch.setenv('CI_MERGE_REQUEST_IID', '42')

        assert GitLabAdapter.detect() is True

    def test_detect_github_actions(self, monkeypatch):
        """Test GitHub Actions detection"""
        monkeypatch.setenv('GITHUB_ACTIONS', 'true')
        monkeypatch.setenv('GITHUB_PR_NUMBER', '10')

        assert GitHubAdapter.detect() is True

    def test_detect_harness_ci(self, monkeypatch):
        """Test Harness CI detection"""
        monkeypatch.setenv('HARNESS_BUILD_ID', 'build-123')
        monkeypatch.setenv('HARNESS_PR_NUMBER', '42')

        assert HarnessAdapter.detect() is True

    def test_detect_no_platform(self, monkeypatch):
        """Test when no CI platform is detected"""
        # Clear all CI environment variables
        for key in os.environ.keys():
            if any(prefix in key for prefix in ['GITLAB', 'GITHUB', 'HARNESS', 'CI_']):
                monkeypatch.delenv(key, raising=False)

        platform = get_platform()
        assert platform is None

    @patch('k8s_validator.platforms.gitlab.gitlab')
    def test_get_platform_by_name_gitlab(self, mock_gitlab_module, monkeypatch):
        """Test getting GitLab platform by explicit name"""
        monkeypatch.setenv('CI_PROJECT_ID', '12345')
        monkeypatch.setenv('CI_MERGE_REQUEST_IID', '42')
        monkeypatch.setenv('GITLAB_TOKEN', 'glpat-test')

        # Mock the gitlab module
        mock_gitlab_module.Gitlab = Mock()

        platform = get_platform('gitlab')
        assert isinstance(platform, GitLabAdapter)

    def test_get_platform_invalid_name(self):
        """Test getting platform with invalid name"""
        platform = get_platform('invalid')
        assert platform is None


# ============================================================================
# GitLab Adapter Tests
# ============================================================================

class TestGitLabAdapter:
    """Test GitLab platform adapter"""

    def test_init_stores_env_vars(self, monkeypatch):
        """Test adapter initialization stores environment variables"""
        monkeypatch.setenv('CI_SERVER_URL', 'https://gitlab.example.com')
        monkeypatch.setenv('CI_PROJECT_ID', '12345')
        monkeypatch.setenv('CI_MERGE_REQUEST_IID', '42')
        monkeypatch.setenv('GITLAB_TOKEN', 'glpat-test-token')

        adapter = GitLabAdapter()

        assert adapter.gitlab_url == 'https://gitlab.example.com'
        assert adapter.project_id == '12345'
        assert adapter.mr_iid == '42'
        assert adapter.token == 'glpat-test-token'

    def test_init_defaults(self):
        """Test adapter initialization with defaults"""
        adapter = GitLabAdapter()

        # Default URL when CI_SERVER_URL not set
        assert adapter.gitlab_url == 'https://gitlab.com'
        assert adapter._client is None
        assert adapter._project is None
        assert adapter._mr is None

    def test_detect_with_all_vars(self, monkeypatch):
        """Test detection returns True when all required vars present"""
        monkeypatch.setenv('GITLAB_CI', 'true')
        monkeypatch.setenv('CI_MERGE_REQUEST_IID', '42')

        assert GitLabAdapter.detect() is True

    def test_detect_missing_gitlab_ci(self, monkeypatch):
        """Test detection returns False when GITLAB_CI missing"""
        monkeypatch.setenv('CI_MERGE_REQUEST_IID', '42')
        monkeypatch.delenv('GITLAB_CI', raising=False)

        assert GitLabAdapter.detect() is False

    def test_detect_missing_mr_iid(self, monkeypatch):
        """Test detection returns False when MR IID missing"""
        monkeypatch.setenv('GITLAB_CI', 'true')
        monkeypatch.delenv('CI_MERGE_REQUEST_IID', raising=False)

        assert GitLabAdapter.detect() is False

    @patch('k8s_validator.platforms.gitlab.gitlab')
    def test_ensure_authenticated_success(self, mock_gitlab_module, monkeypatch):
        """Test successful authentication"""
        monkeypatch.setenv('CI_PROJECT_ID', '12345')
        monkeypatch.setenv('CI_MERGE_REQUEST_IID', '42')
        monkeypatch.setenv('GITLAB_TOKEN', 'glpat-test')

        # Mock gitlab module and API chain
        mock_gl = Mock()
        mock_project = Mock()
        mock_mr = Mock()

        mock_gitlab_module.Gitlab = Mock(return_value=mock_gl)
        mock_gl.projects.get.return_value = mock_project
        mock_project.mergerequests.get.return_value = mock_mr

        adapter = GitLabAdapter()
        result = adapter._ensure_authenticated()

        assert result is True
        assert adapter._mr == mock_mr
        mock_gl.auth.assert_called_once()

    @patch('k8s_validator.platforms.gitlab.gitlab', None)
    def test_ensure_authenticated_no_gitlab_module(self):
        """Test authentication fails when gitlab module not available"""
        adapter = GitLabAdapter()
        result = adapter._ensure_authenticated()

        assert result is False

    @patch('k8s_validator.platforms.gitlab.gitlab')
    def test_post_comment_success(self, mock_gitlab_module, monkeypatch):
        """Test posting comment to GitLab MR"""
        monkeypatch.setenv('CI_PROJECT_ID', '12345')
        monkeypatch.setenv('CI_MERGE_REQUEST_IID', '42')
        monkeypatch.setenv('GITLAB_TOKEN', 'glpat-test')

        # Mock API
        mock_gl = Mock()
        mock_project = Mock()
        mock_mr = Mock()

        mock_gitlab_module.Gitlab = Mock(return_value=mock_gl)
        mock_gl.projects.get.return_value = mock_project
        mock_project.mergerequests.get.return_value = mock_mr

        adapter = GitLabAdapter()
        result = adapter.post_comment("Test validation results")

        assert result is True
        mock_mr.notes.create.assert_called_once_with({'body': 'Test validation results'})

    @patch('k8s_validator.platforms.gitlab.subprocess.run')
    def test_get_changed_files_success(self, mock_run, monkeypatch, tmp_path):
        """Test getting changed files from GitLab MR"""
        # Create temporary files
        test_file1 = tmp_path / "deployment.yaml"
        test_file1.write_text("kind: Deployment")
        test_file2 = tmp_path / "service.yaml"
        test_file2.write_text("kind: Service")

        # Mock git diff output
        mock_result = Mock()
        mock_result.stdout = f"{test_file1}\n{test_file2}\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        adapter = GitLabAdapter()

        # Change to tmp directory so files exist
        monkeypatch.chdir(tmp_path)
        files = adapter.get_changed_files()

        assert len(files) == 2
        assert all(isinstance(f, Path) for f in files)

    @patch('k8s_validator.platforms.gitlab.subprocess.run')
    def test_get_changed_files_git_error(self, mock_run):
        """Test handling git command errors"""
        # Mock git command failure
        mock_result = Mock()
        mock_result.returncode = 128
        mock_run.return_value = mock_result

        adapter = GitLabAdapter()
        files = adapter.get_changed_files()

        assert files == []

    @patch('k8s_validator.platforms.gitlab.gitlab')
    def test_get_metadata(self, mock_gitlab_module, monkeypatch):
        """Test getting MR metadata"""
        monkeypatch.setenv('CI_SERVER_URL', 'https://gitlab.example.com')
        monkeypatch.setenv('CI_PROJECT_ID', '12345')
        monkeypatch.setenv('CI_MERGE_REQUEST_IID', '42')
        monkeypatch.setenv('GITLAB_TOKEN', 'glpat-test')

        # Mock API
        mock_gl = Mock()
        mock_project = Mock()
        mock_mr = Mock()
        mock_mr.title = "Test MR"
        mock_mr.author = {"username": "testuser"}
        mock_mr.web_url = "https://gitlab.example.com/project/repo/-/merge_requests/42"
        mock_mr.source_branch = "feature-branch"
        mock_mr.target_branch = "main"

        mock_gitlab_module.Gitlab = Mock(return_value=mock_gl)
        mock_gl.projects.get.return_value = mock_project
        mock_project.mergerequests.get.return_value = mock_mr

        adapter = GitLabAdapter()
        metadata = adapter.get_metadata()

        assert metadata['platform'] == 'gitlab'
        assert metadata['project_id'] == '12345'
        assert metadata['mr_iid'] == '42'
        assert metadata['mr_title'] == 'Test MR'
        assert metadata['mr_author'] == 'testuser'


# ============================================================================
# GitHub Adapter Tests
# ============================================================================

class TestGitHubAdapter:
    """Test GitHub platform adapter"""

    def test_init_stores_env_vars(self, monkeypatch):
        """Test adapter initialization stores environment variables"""
        monkeypatch.setenv('GITHUB_REPOSITORY', 'owner/repo')
        monkeypatch.setenv('GITHUB_PR_NUMBER', '10')
        monkeypatch.setenv('GITHUB_TOKEN', 'ghp_test_token')

        adapter = GitHubAdapter()

        assert adapter.repository == 'owner/repo'
        assert adapter.pr_number == '10'
        assert adapter.token == 'ghp_test_token'

    def test_detect_with_all_vars(self, monkeypatch):
        """Test detection returns True when all required vars present"""
        monkeypatch.setenv('GITHUB_ACTIONS', 'true')
        monkeypatch.setenv('GITHUB_PR_NUMBER', '10')

        assert GitHubAdapter.detect() is True

    def test_detect_missing_pr_number(self, monkeypatch):
        """Test detection returns False when PR number missing"""
        monkeypatch.setenv('GITHUB_ACTIONS', 'true')
        monkeypatch.delenv('GITHUB_PR_NUMBER', raising=False)

        assert GitHubAdapter.detect() is False

    @patch('k8s_validator.platforms.github.Github')
    def test_ensure_authenticated_success(self, mock_github_class, monkeypatch):
        """Test successful authentication"""
        monkeypatch.setenv('GITHUB_REPOSITORY', 'owner/repo')
        monkeypatch.setenv('GITHUB_PR_NUMBER', '10')
        monkeypatch.setenv('GITHUB_TOKEN', 'ghp_test')

        # Mock GitHub API chain
        mock_gh = Mock()
        mock_repo = Mock()
        mock_pr = Mock()

        mock_github_class.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        adapter = GitHubAdapter()
        result = adapter._ensure_authenticated()

        assert result is True
        assert adapter._pr == mock_pr
        mock_repo.get_pull.assert_called_once_with(10)

    @patch('k8s_validator.platforms.github.Github', None)
    def test_ensure_authenticated_no_github_module(self):
        """Test authentication fails when Github module not available"""
        adapter = GitHubAdapter()
        result = adapter._ensure_authenticated()

        assert result is False

    @patch('k8s_validator.platforms.github.Github')
    def test_post_comment_success(self, mock_github_class, monkeypatch):
        """Test posting comment to GitHub PR"""
        monkeypatch.setenv('GITHUB_REPOSITORY', 'owner/repo')
        monkeypatch.setenv('GITHUB_PR_NUMBER', '10')
        monkeypatch.setenv('GITHUB_TOKEN', 'ghp_test')

        # Mock API
        mock_gh = Mock()
        mock_repo = Mock()
        mock_pr = Mock()

        mock_github_class.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        adapter = GitHubAdapter()
        result = adapter.post_comment("Test validation results")

        assert result is True
        mock_pr.create_issue_comment.assert_called_once_with('Test validation results')

    @patch('k8s_validator.platforms.github.subprocess.run')
    def test_get_changed_files_success(self, mock_run, monkeypatch, tmp_path):
        """Test getting changed files from GitHub PR"""
        # Create temporary files
        test_file = tmp_path / "deployment.yaml"
        test_file.write_text("kind: Deployment")

        # Mock git diff output
        mock_result = Mock()
        mock_result.stdout = f"{test_file}\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        adapter = GitHubAdapter()

        # Change to tmp directory so files exist
        monkeypatch.chdir(tmp_path)
        files = adapter.get_changed_files()

        assert len(files) == 1
        assert isinstance(files[0], Path)

    @patch('k8s_validator.platforms.github.Github')
    def test_get_metadata(self, mock_github_class, monkeypatch):
        """Test getting PR metadata"""
        monkeypatch.setenv('GITHUB_REPOSITORY', 'owner/repo')
        monkeypatch.setenv('GITHUB_PR_NUMBER', '10')
        monkeypatch.setenv('GITHUB_TOKEN', 'ghp_test')

        # Mock API
        mock_gh = Mock()
        mock_repo = Mock()
        mock_pr = Mock()
        mock_pr.title = "Test PR"
        mock_pr.user.login = "testuser"
        mock_pr.html_url = "https://github.com/owner/repo/pull/10"
        mock_pr.head.ref = "feature"
        mock_pr.base.ref = "main"

        mock_github_class.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        adapter = GitHubAdapter()
        metadata = adapter.get_metadata()

        assert metadata['platform'] == 'github'
        assert metadata['repository'] == 'owner/repo'
        assert metadata['pr_number'] == '10'
        assert metadata['pr_title'] == 'Test PR'


# ============================================================================
# Harness Adapter Tests
# ============================================================================

class TestHarnessAdapter:
    """Test Harness platform adapter"""

    def test_init_stores_env_vars(self, monkeypatch):
        """Test adapter initialization stores environment variables"""
        monkeypatch.setenv('HARNESS_API_KEY', 'pat.test.key')
        monkeypatch.setenv('HARNESS_ACCOUNT_ID', 'account-456')
        monkeypatch.setenv('HARNESS_PR_NUMBER', '42')
        monkeypatch.setenv('HARNESS_REPO_NAME', 'owner/repo')

        adapter = HarnessAdapter()

        assert adapter.api_key == 'pat.test.key'
        assert adapter.account_id == 'account-456'
        assert adapter.pr_number == '42'
        assert adapter.repo_name == 'owner/repo'

    def test_detect_with_all_vars(self, monkeypatch):
        """Test detection returns True when all required vars present"""
        monkeypatch.setenv('HARNESS_BUILD_ID', 'build-123')
        monkeypatch.setenv('HARNESS_PR_NUMBER', '42')

        assert HarnessAdapter.detect() is True

    def test_detect_missing_build_id(self, monkeypatch):
        """Test detection returns False when build ID missing"""
        monkeypatch.setenv('HARNESS_PR_NUMBER', '42')
        monkeypatch.delenv('HARNESS_BUILD_ID', raising=False)

        assert HarnessAdapter.detect() is False

    @patch('k8s_validator.platforms.harness.requests.post')
    def test_post_comment_success(self, mock_post, monkeypatch):
        """Test posting comment to Harness PR"""
        monkeypatch.setenv('HARNESS_API_KEY', 'pat.test.key')
        monkeypatch.setenv('HARNESS_ACCOUNT_ID', 'account-456')
        monkeypatch.setenv('HARNESS_PR_NUMBER', '42')
        monkeypatch.setenv('HARNESS_REPO_NAME', 'owner/repo')

        mock_response = Mock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        adapter = HarnessAdapter()
        result = adapter.post_comment("Test validation results")

        assert result is True
        mock_post.assert_called_once()

        # Verify API call details
        call_args = mock_post.call_args
        assert 'harness.io' in call_args[0][0]
        assert call_args[1]['headers']['x-api-key'] == 'pat.test.key'
        assert call_args[1]['json']['text'] == 'Test validation results'

    @patch('k8s_validator.platforms.harness.requests.post')
    def test_post_comment_api_error(self, mock_post, monkeypatch):
        """Test handling Harness API errors"""
        monkeypatch.setenv('HARNESS_API_KEY', 'pat.test.key')
        monkeypatch.setenv('HARNESS_ACCOUNT_ID', 'account-456')
        monkeypatch.setenv('HARNESS_PR_NUMBER', '42')
        monkeypatch.setenv('HARNESS_REPO_NAME', 'owner/repo')

        mock_response = Mock()
        mock_response.status_code = 403
        mock_post.return_value = mock_response

        adapter = HarnessAdapter()
        result = adapter.post_comment("Test comment")

        assert result is False

    @patch('k8s_validator.platforms.harness.requests.post')
    def test_post_comment_missing_required_vars(self, mock_post, monkeypatch):
        """Test post comment fails when required vars missing"""
        monkeypatch.setenv('HARNESS_API_KEY', 'pat.test.key')
        # Missing account_id and pr_number

        adapter = HarnessAdapter()
        result = adapter.post_comment("Test comment")

        assert result is False
        mock_post.assert_not_called()

    @patch('k8s_validator.platforms.harness.subprocess.run')
    def test_get_changed_files_success(self, mock_run, monkeypatch, tmp_path):
        """Test getting changed files from Harness PR"""
        # Create temporary files
        test_file = tmp_path / "values.yaml"
        test_file.write_text("image: nginx")

        # Mock git diff output
        mock_result = Mock()
        mock_result.stdout = f"{test_file}\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        adapter = HarnessAdapter()

        # Change to tmp directory so files exist
        monkeypatch.chdir(tmp_path)
        files = adapter.get_changed_files()

        assert len(files) == 1
        assert isinstance(files[0], Path)

    @patch('k8s_validator.platforms.harness.subprocess.run')
    def test_get_changed_files_empty(self, mock_run):
        """Test handling empty changed files list"""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        adapter = HarnessAdapter()
        files = adapter.get_changed_files()

        assert files == []

    def test_get_metadata(self, monkeypatch):
        """Test getting PR metadata"""
        monkeypatch.setenv('HARNESS_ACCOUNT_ID', 'account-456')
        monkeypatch.setenv('HARNESS_PR_NUMBER', '42')
        monkeypatch.setenv('HARNESS_REPO_NAME', 'owner/repo')

        adapter = HarnessAdapter()
        metadata = adapter.get_metadata()

        assert metadata['platform'] == 'harness'
        assert metadata['account_id'] == 'account-456'
        assert metadata['pr_number'] == '42'
        assert metadata['repo_name'] == 'owner/repo'
