#ifndef ZED_CLIENT_H
#define ZED_CLIENT_H
#include <stdbool.h>
typedef struct { const char *base_url; const char *bearer_token; } zed_client;
zed_client zed_client_new(const char *base_url, const char *bearer_token);
bool zed_client_health(const zed_client *client);
#endif
