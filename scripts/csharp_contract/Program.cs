using System.Collections;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Serialization;
using LJ.DTO;
using LJ.DTO.Engine;

// Read the same package and Web serialization rules as ConditionAlgorithm.
if (args.Length != 1) throw new ArgumentException("Expected output JSON path.");
var json = new JsonSerializerOptions(JsonSerializerDefaults.Web);
var nullability = new NullabilityInfoContext();
var types = new Dictionary<string, object>();
var queued = new HashSet<Type>();
Visit(typeof(ProjectDTO));
Visit(typeof(SimData));
var sample = new
{
    frameData = Sample(typeof(SimData), 0),
    projectDto = Sample(typeof(ProjectDTO), 0),
    forceType = 1,
    satId = "1001"
};
var output = new
{
    assembly = typeof(ProjectDTO).Assembly.GetName().FullName,
    models = types,
    conditionData = JsonSerializer.SerializeToElement(sample, json)
};
File.WriteAllText(args[0], JsonSerializer.Serialize(output, new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine($"Exported {types.Count} DTO models.");

void Visit(Type type)
{
    type = Nullable.GetUnderlyingType(type) ?? type;
    if (type.IsArray) { Visit(type.GetElementType()!); return; }
    if (type.IsGenericType) { foreach (var item in type.GetGenericArguments()) Visit(item); return; }
    if (type.Namespace?.StartsWith("LJ.DTO") != true || type.Name.StartsWith("Vector") || !queued.Add(type)) return;
    var instance = Activator.CreateInstance(type)!;
    var properties = Properties(type).Select(property =>
    {
        Visit(property.PropertyType);
        JsonElement? value = null;
        try { value = JsonSerializer.SerializeToElement(property.GetValue(instance), property.PropertyType, json); }
        catch (InvalidOperationException) { } // Uninitialized JsonElement.
        return new
        {
            name = property.Name,
            alias = property.GetCustomAttribute<JsonPropertyNameAttribute>()?.Name
                ?? JsonNamingPolicy.CamelCase.ConvertName(property.Name),
            type = Shape(property.PropertyType),
            nullable = Nullable.GetUnderlyingType(property.PropertyType) is not null
                || nullability.Create(property).ReadState == NullabilityState.Nullable,
            readOnly = !property.CanWrite,
            @default = value
        };
    }).ToArray();
    types[type.Name] = new { source = type.FullName, properties };
}

object Shape(Type type)
{
    type = Nullable.GetUnderlyingType(type) ?? type;
    if (type == typeof(byte[])) return new { kind = "bytes" };
    if (type.IsArray) return new { kind = "list", item = Shape(type.GetElementType()!) };
    if (type.IsGenericType)
    {
        var arguments = type.GetGenericArguments();
        if (type.GetGenericTypeDefinition() == typeof(Dictionary<,>))
            return new { kind = "dict", key = Shape(arguments[0]), item = Shape(arguments[1]) };
        if (type.GetGenericTypeDefinition() == typeof(List<>)) return new { kind = "list", item = Shape(arguments[0]) };
        throw new NotSupportedException(type.FullName);
    }
    var kind = type == typeof(string) ? "str" : type == typeof(bool) ? "bool"
        : type == typeof(int) || type == typeof(long) || type == typeof(short) ? "int"
        : type == typeof(double) || type == typeof(float) ? "float"
        : type == typeof(DateTime) || type == typeof(DateTimeOffset) ? "datetime"
        : type == typeof(object) || type == typeof(JsonElement) ? "json" : "model";
    return new { kind, name = type.Name };
}

PropertyInfo[] Properties(Type type) => type.GetProperties(BindingFlags.Public | BindingFlags.Instance)
    .Where(property => property.GetIndexParameters().Length == 0
        && property.GetCustomAttribute<JsonIgnoreAttribute>()?.Condition != JsonIgnoreCondition.Always)
    .OrderBy(property => property.MetadataToken).ToArray();

object? Sample(Type type, int depth)
{
    type = Nullable.GetUnderlyingType(type) ?? type;
    if (type == typeof(string)) return "sample";
    if (type == typeof(bool)) return true;
    if (type == typeof(long)) return 1001L;
    if (type == typeof(int)) return 1;
    if (type == typeof(double)) return 1.5;
    if (type == typeof(DateTime)) return new DateTime(2026, 11, 13, 10, 0, 0, DateTimeKind.Utc);
    if (type == typeof(DateTimeOffset)) return new DateTimeOffset(2026, 11, 13, 10, 0, 0, TimeSpan.Zero);
    if (type == typeof(Vector3d)) return new Vector3d(1, 2, 3);
    if (type == typeof(Vector4d)) return new Vector4d(1, 2, 3, 4);
    if (type == typeof(Vector6d)) return new Vector6d(1, 2, 3, 4, 5, 6);
    if (type == typeof(JsonElement)) return JsonSerializer.SerializeToElement(new { custom = new object?[] { true, null, "002" } });
    if (type == typeof(object)) return new Dictionary<string, object?> { ["custom"] = new object?[] { true, null, "002" } };
    if (type == typeof(byte[])) return new byte[] { 1, 2, 255 };
    if (type.IsArray)
    {
        var element = type.GetElementType()!;
        var array = Array.CreateInstance(element, 3);
        for (var i = 0; i < 3; i++) array.SetValue(Sample(element, depth + 1), i);
        return array;
    }
    if (type.IsGenericType)
    {
        if (type.GetGenericTypeDefinition() == typeof(List<>))
        {
            var list = (IList)Activator.CreateInstance(type)!;
            if (depth < 9) list.Add(Sample(type.GetGenericArguments()[0], depth + 1));
            return list;
        }
        var dictionary = (IDictionary)Activator.CreateInstance(type)!;
        var arguments = type.GetGenericArguments();
        dictionary.Add(arguments[0] == typeof(string) ? "sample" : 1001L, Sample(arguments[1], depth + 1));
        return dictionary;
    }
    var value = Activator.CreateInstance(type)!;
    foreach (var property in Properties(type).Where(property => property.CanWrite))
    {
        if (property.Name == "Timestamp") property.SetValue(value, 1794535200000L);
        else property.SetValue(value, Sample(property.PropertyType, depth + 1));
    }
    return value;
}
