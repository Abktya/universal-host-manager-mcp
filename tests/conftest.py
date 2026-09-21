"""Paylaşılan pytest fixture'ları ve test-zamanı ortam kurulumu.

Ortam değişkenleri burada bir fixture İÇİNDE DEĞİL, modül seviyesinde
ayarlanır. Çünkü pytest, test modüllerini "collection" aşamasında,
herhangi bir fixture (session-scoped olsa bile) çalışmadan ÖNCE import
eder. server.py da import anında Auth0 doğrulaması yaptığı için, bu
değişkenler burada, en tepede ayarlanmazsa ilk `from
universal_host_manager_mcp import server` satırında RuntimeError
fırlar.
"""

import os
import tempfile

import pytest

_workspace = tempfile.mkdtemp(prefix="uhm-test-workspace-")
os.environ.setdefault("ALLOW_INSECURE_NO_AUTH", "true")
os.environ.setdefault("MCP_WORKSPACE_DIR", _workspace)
os.environ.setdefault("HOST", "127.0.0.1")
os.environ.setdefault("PORT", "8765")
os.environ.setdefault("LOG_COMMANDS", "false")
os.environ.setdefault("FASTMCP_CHECK_FOR_UPDATES", "off")


@pytest.fixture
def call_tool():
    """@mcp.tool() ile süslenmiş bir fonksiyonu sürümden bağımsız çağıran
    bir yardımcı döndürür.

    fastmcp 2.13'te @mcp.tool() bir FunctionTool nesnesi döndürür (asıl
    fonksiyona .fn üzerinden erişilir); fastmcp 3.x/4.x'te ise düz
    fonksiyonun kendisini döndürür.

    Bu bilerek "tests.conftest"ten import edilen düz bir fonksiyon değil,
    bir pytest fixture'ı: "tests/" paketinin sys.path üzerinden import
    edilebilir olup olmadığına bağlı değil (pytest'in kendi dependency
    injection mekanizmasını kullanıyor), bu yüzden hem "python -m pytest"
    hem de doğrudan "pytest" komutuyla, calisma dizininden bagimsiz
    calisir.
    """

    def _call(tool, *args, **kwargs):
        fn = getattr(tool, "fn", tool)
        return fn(*args, **kwargs)

    return _call
