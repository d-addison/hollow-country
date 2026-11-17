// Strict bounded ASCII JSON tokens before native LoadData. No inherited DTO keys.
class HCInteriorTemplatesStrict
{
    static string Keys(string schema)

    {
        if (schema == "index")

        {
            return "SchemaVersion Kind WorldName Build PackId SourcePin Frame Provisional Sources ClassFiles TemplateFiles FurnishFiles GroupFiles";
        }
        if (schema == "file")

        {
            return "File Sha256";
        }
        if (schema == "template-file")

        {
            return "File BuildingClass Sha256";
        }
        if (schema == "classes")

        {
            return "SchemaVersion Chunk Rows";
        }
        if (schema == "class-row")

        {
            return "BuildingClass Rooms Furniture Search";
        }
        if (schema == "furnish")

        {
            return "SchemaVersion Chunk Rows";
        }
        if (schema == "furnish-row")

        {
            return "Slot BuildingClass Position Yaw Props History";
        }
        if (schema == "groups")

        {
            return "SchemaVersion Chunk Groups";
        }
        if (schema == "group")

        {
            return "Id Usages Container Categories Tags Items";
        }
        if (schema == "template")

        {
            return "SchemaVersion BuildingClass TemplateId Box Evidence Rooms KeepOuts PropSlots SearchSites";
        }
        if (schema == "box")

        {
            return "Min Max";
        }
        if (schema == "evidence")

        {
            return "Kind RunId Sha256";
        }
        if (schema == "room")

        {
            return "Id Label Min Max Anchor FloorY Cells";
        }
        if (schema == "keepout")

        {
            return "Kind Index Min Max";
        }
        if (schema == "prop")

        {
            return "Id Room Type Position Orientation Bounds History";
        }
        if (schema == "site")

        {
            return "Id Room Center Radius Source Points Groups";
        }
        return "";
    }

    static bool Hex(string value, int length)

    {
        if (value.Length() != length)

        {
            return false;
        }
        int i = 0;
        while (i < length)

        {
            string ch = value.Get(i);
            int code = ch.ToAscii();
            if (!((code >= 48 && code <= 57) || (code >= 97 && code <= 102)))

            {
                return false;
            }
            i = i + 1;
        }
        return true;
    }

    static bool SourceName(string key)

    {
        if (key == "mapgroupproto" || key == "mapgrouppos" || key == "types" || key == "cfgspawnabletypes" || key == "cfglimitsdefinition" || key == "generator" || key == "search-generator")

        {
            return true;
        }
        if (key.Length() != 39 || key.Substring(0, 7) != "census-")

        {
            return false;
        }
        return Hex(key.Substring(7, 32), 32);
    }

    static int ArrayCap(string schema)

    {
        if (schema == "@template-file")
        {
            return 512;
        }
        if (schema == "@file")
        {
            return 64;
        }
        if (schema == "@class-row")
        {
            return 160;
        }
        if (schema == "@furnish-row")
        {
            return 128;
        }
        if (schema == "@room")
        {
            return 16;
        }
        if (schema == "@keepout")
        {
            return 32;
        }
        if (schema == "@prop")
        {
            return 20;
        }
        if (schema == "@site")
        {
            return 24;
        }
        if (schema == "@number")
        {
            return 3;
        }
        if (schema == "@evidence")
        {
            return 512;
        }
        if (schema == "@group")

        {
            return 512;
        }
        // A 32,767-byte file cannot contain more than 8,192 list values with
        // the nonempty, unique text/index semantics checked after parsing.
        return 8192;
    }

    static string Child(string schema, string key)

    {
        if (schema == "sources")
        {
            return "text";
        }
        if (key == "SchemaVersion" || key == "Chunk" || key == "Index" || key == "Room" || key == "Cells" || key == "Slot")
        {
            return "integer";
        }
        if (key == "Id" && schema != "group")
        {
            return "integer";
        }
        if (key == "Provisional")
        {
            return "boolean";
        }
        if (key == "Sources")
        {
            return "sources";
        }
        if (key == "ClassFiles" || key == "FurnishFiles" || key == "GroupFiles")
        {
            return "@file";
        }
        if (key == "TemplateFiles")
        {
            return "@template-file";
        }
        if (key == "Rows")

        {
            if (schema == "classes")
            {
                return "@class-row";
            }
            return "@furnish-row";
        }
        if (key == "Groups")

        {
            if (schema == "groups")
            {
                return "@group";
            }
            return "@text";
        }
        if (key == "Box" || key == "Bounds")
        {
            return "box";
        }
        if (key == "Evidence")
        {
            return "@evidence";
        }
        if (key == "Rooms" && schema == "template")
        {
            return "@room";
        }
        if (key == "KeepOuts")
        {
            return "@keepout";
        }
        if (key == "PropSlots")
        {
            return "@prop";
        }
        if (key == "SearchSites")
        {
            return "@site";
        }
        if (key == "Position" || key == "Orientation" || key == "Min" || key == "Max" || key == "Anchor" || key == "Center")
        {
            return "@number";
        }
        if (key == "FloorY" || key == "Radius" || key == "Yaw")
        {
            return "number";
        }
        if (key == "Points" || key == "Props")
        {
            return "@integer";
        }
        if (key == "Items" || key == "Categories" || key == "Tags" || key == "Usages" || (key == "History" && schema == "prop"))
        {
            return "@text";
        }
        return "text";
    }

    static int Code(HCInteriorTemplateCursor cursor)

    {
        if (cursor.Index >= cursor.Content.Length())

        {
            return -1;
        }
        string ch = cursor.Content.Get(cursor.Index);
        return ch.ToAscii();
    }

    static void Space(HCInteriorTemplateCursor cursor)

    {
        int code = Code(cursor);
        while (code == 32 || code == 9 || code == 10 || code == 13)

        {
            cursor.Index = cursor.Index + 1;
            code = Code(cursor);
        }
    }

    static bool Take(HCInteriorTemplateCursor cursor, int expected)

    {
        Space(cursor);
        if (Code(cursor) != expected)

        {
            return false;
        }
        cursor.Index = cursor.Index + 1;
        return true;
    }

    static string StringToken(HCInteriorTemplateCursor cursor, bool key)

    {
        if (!Take(cursor, 34))

        {
            cursor.Failed = true;
            return "";
        }
        int begin = cursor.Index;
        while (cursor.Index < cursor.Content.Length())

        {
            int code = Code(cursor);
            if (code == 34)

            {
                int length = cursor.Index - begin;
                string result = cursor.Content.Substring(begin, length);
                cursor.Index = cursor.Index + 1;
                return result;
            }
            if (code < 32 || code > 126)

            {
                cursor.Failed = true;
                return "";
            }
            if (code == 92)

            {
                if (key)

                {
                    cursor.Failed = true;
                    return "";
                }
                cursor.Index = cursor.Index + 1;
                code = Code(cursor);
                if (code == 117)

                {
                    int end = cursor.Index + 5;
                    cursor.Index = cursor.Index + 1;
                    while (cursor.Index < end)

                    {
                        code = Code(cursor);
                        if (!((code >= 48 && code <= 57) || (code >= 65 && code <= 70) || (code >= 97 && code <= 102)))

                        {
                            cursor.Failed = true;
                            return "";
                        }
                        cursor.Index = cursor.Index + 1;
                    }
                    continue;
                }
                if (code != 34 && code != 92 && code != 47 && code != 98 && code != 102 && code != 110 && code != 114 && code != 116)

                {
                    cursor.Failed = true;
                    return "";
                }
            }
            cursor.Index = cursor.Index + 1;
        }
        cursor.Failed = true;
        return "";
    }

    static bool IntegerToken(HCInteriorTemplateCursor cursor, int begin)

    {
        if (cursor.Index - begin > 11)

        {
            return false;
        }
        int offset = begin;
        if (cursor.Content.Get(offset) == "-")

        {
            offset = offset + 1;
        }
        int amount = 0;
        while (offset < cursor.Index)

        {
            string ch = cursor.Content.Get(offset);
            int digit = ch.ToAscii() - 48;
            if (amount > 214748364 || (amount == 214748364 && digit > 7))

            {
                return false;
            }
            amount = amount * 10 + digit;
            offset = offset + 1;
        }
        return true;
    }

    static bool Value(HCInteriorTemplateCursor cursor, string schema, int depth)

    {
        cursor.Nodes = cursor.Nodes + 1;
        if (cursor.Failed || depth > 12 || cursor.Nodes > 16384)

        {
            return false;
        }
        Space(cursor);
        if (schema == "text")

        {
            StringToken(cursor, false);
            return !cursor.Failed;
        }
        if (schema == "boolean")

        {
            int remaining = cursor.Content.Length() - cursor.Index;
            if (remaining >= 4)

            {
                string yes = cursor.Content.Substring(cursor.Index, 4);
                if (yes == "true")

                {
                    cursor.Index = cursor.Index + 4;
                    return true;
                }
            }
            if (remaining >= 5)

            {
                string no = cursor.Content.Substring(cursor.Index, 5);
                if (no == "false")

                {
                    cursor.Index = cursor.Index + 5;
                    return true;
                }
            }
            return false;
        }
        if (schema == "integer" || schema == "number")

        {
            int begin = cursor.Index;
            if (Code(cursor) == 45)

            {
                cursor.Index = cursor.Index + 1;
            }
            int code = Code(cursor);
            if (code < 48 || code > 57)

            {
                return false;
            }
            if (code == 48)

            {
                cursor.Index = cursor.Index + 1;
            }
            else

            {
                while (code >= 48 && code <= 57)

                {
                    cursor.Index = cursor.Index + 1;
                    code = Code(cursor);
                }
            }
            if (schema == "number" && Code(cursor) == 46)

            {
                cursor.Index = cursor.Index + 1;
                int fraction = cursor.Index;
                code = Code(cursor);
                while (code >= 48 && code <= 57)

                {
                    cursor.Index = cursor.Index + 1;
                    code = Code(cursor);
                }
                if (cursor.Index == fraction)

                {
                    return false;
                }
            }
            code = Code(cursor);
            if (schema == "number" && (code == 69 || code == 101))

            {
                cursor.Index = cursor.Index + 1;
                code = Code(cursor);
                if (code == 43 || code == 45)

                {
                    cursor.Index = cursor.Index + 1;
                }
                int exponent = cursor.Index;
                code = Code(cursor);
                while (code >= 48 && code <= 57)

                {
                    cursor.Index = cursor.Index + 1;
                    code = Code(cursor);
                }
                if (cursor.Index == exponent)

                {
                    return false;
                }
            }
            if (schema == "integer")

            {
                // Reject long integer tokens before native parsing can wrap.
                return IntegerToken(cursor, begin);
            }
            return cursor.Index - begin <= 32;
        }
        if (schema.Length() > 1 && schema.Get(0) == "@")

        {
            if (!Take(cursor, 91))

            {
                return false;
            }
            int childLength = schema.Length() - 1;
            string child = schema.Substring(1, childLength);
            int count = 0;
            Space(cursor);
            if (Code(cursor) == 93)

            {
                cursor.Index = cursor.Index + 1;
                return true;
            }
            while (count < ArrayCap(schema))

            {
                if (!Value(cursor, child, depth + 1))

                {
                    return false;
                }
                count = count + 1;
                Space(cursor);
                if (Code(cursor) == 93)

                {
                    cursor.Index = cursor.Index + 1;
                    return true;
                }
                if (!Take(cursor, 44))

                {
                    return false;
                }
            }
            return false;
        }
        string keys = Keys(schema);
        if ((keys.Length() == 0 && schema != "sources") || !Take(cursor, 123))

        {
            return false;
        }
        array<string> required = new array<string>();
        array<string> seen = new array<string>();
        keys.Split(" ", required);
        int fieldCap = required.Count();
        if (schema == "sources")

        {
            fieldCap = 520;
        }
        int fields = 0;
        while (fields < fieldCap)

        {
            Space(cursor);
            int keyBegin = cursor.Index + 1;
            string key = StringToken(cursor, true);
            if (cursor.Failed || seen.Find(key) >= 0)

            {
                return false;
            }
            if (schema == "sources")

            {
                if (!SourceName(key))

                {
                    return false;
                }
            }
            else

            {
                if (required.Find(key) < 0)

                {
                    return false;
                }
            }
            seen.Insert(key);
            if (schema == "furnish-row" && key == "Slot")

            {
                int prefixLength = keyBegin - cursor.CopyFrom;
                string prefixText = cursor.Content.Substring(cursor.CopyFrom, prefixLength);
                cursor.NativeText = cursor.NativeText + prefixText + "SlotId";
                cursor.CopyFrom = keyBegin + key.Length();
            }
            if (!Take(cursor, 58))

            {
                return false;
            }
            string valueSchema = Child(schema, key);
            if (!Value(cursor, valueSchema, depth + 1))

            {
                return false;
            }
            fields = fields + 1;
            Space(cursor);
            if (Code(cursor) == 125)

            {
                cursor.Index = cursor.Index + 1;
                if (schema == "sources")

                {
                    return fields >= 8;
                }
                return fields == required.Count();
            }
            if (!Take(cursor, 44))

            {
                return false;
            }
        }
        return false;
    }

    static string NativeText(string content, string schema)

    {
        if (content.Length() < 1 || content.Length() > 32767)

        {
            return "";
        }
        HCInteriorTemplateCursor cursor = new HCInteriorTemplateCursor;
        cursor.Content = content;
        if (!Value(cursor, schema, 0))

        {
            return "";
        }
        Space(cursor);
        if (cursor.Failed || cursor.Index != content.Length())

        {
            return "";
        }
        int remaining = content.Length() - cursor.CopyFrom;
        string tail = content.Substring(cursor.CopyFrom, remaining);
        return cursor.NativeText + tail;
    }
}
