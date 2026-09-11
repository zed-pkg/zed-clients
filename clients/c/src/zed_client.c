#include "zed_client.h"
zed_client zed_client_new(const char *base_url, const char *bearer_token) {
  zed_client value = {base_url, bearer_token}; return value;
}
bool zed_client_health(const zed_client *client) { return client != 0 && client->base_url != 0; }
