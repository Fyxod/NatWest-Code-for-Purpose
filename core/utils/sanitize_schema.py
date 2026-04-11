def sanitize_schema(schema_dict):
    if isinstance(schema_dict, dict):
        schema_dict.pop("additionalProperties", None)
        for v in schema_dict.values():
            sanitize_schema(v)
    elif isinstance(schema_dict, list):
        for v in schema_dict:
            sanitize_schema(v)
    return schema_dict
