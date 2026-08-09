package io.zedpkg.zed;
import java.net.URI;
public record ZedClient(URI baseUri, String bearerToken) {}
