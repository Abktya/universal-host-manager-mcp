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

_workspace = tempfile.mkdtemp(prefix="uhm-test-workspace-")
os.environ.setdefault("ALLOW_INSECURE_NO_AUTH", "true")
os.environ.setdefault("MCP_WORKSPACE_DIR", _workspace)
os.environ.setdefault("HOST", "127.0.0.1")
os.environ.setdefault("PORT", "8765")
os.environ.setdefault("LOG_COMMANDS", "false")
os.environ.setdefault("FASTMCP_CHECK_FOR_UPDATES", "off")


def call_tool(tool, *args, **kwargs):
    """@mcp.tool() ile süslenmiş bir fonksiyonu sürümden bağımsız çağırır.

    fastmcp 2.13'te @mcp.tool() bir FunctionTool nesnesi döndürür (asıl
    fonksiyona .fn üzerinden erişilir); fastmcp 3.x/4.x'te ise düz
    fonksiyonun kendisini döndürür. Bu yardımcı, testlerin hangi
    fastmcp sürümü kurulu olursa olsun aynı şekilde yazılabilmesini
    sağlar.
    """
    fn = getattr(tool, "fn", tool)
    return fn(*args, **kwargs)
