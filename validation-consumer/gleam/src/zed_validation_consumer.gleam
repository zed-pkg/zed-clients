import gleam/dynamic.{type Dynamic}
import zed_validation

pub fn validate_request_meta(value: Dynamic) { zed_validation.decode_request_meta(value) }
