import "@typespec/json-schema";
using TypeSpec.JsonSchema;
namespace Zed.Admission;

// Independent authored test authority, not generated from JSON Schema.
@id("PackageRef")
model PackageRef {
  name: string;
  version: string;
  integrity?: string;
}
