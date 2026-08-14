package io.zedpkg.zed
import java.net.URI
data class ZedClient(val baseUrl: URI, val bearerToken: String? = null) {
  suspend fun health(): Boolean = baseUrl.toString().isNotEmpty()
}
