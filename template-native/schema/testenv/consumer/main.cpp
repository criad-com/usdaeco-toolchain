#include "pxr/pxr.h"
#include "usdAecoExampleNative/record.h"
#include "pxr/usd/usd/stage.h"
#include "pxr/base/tf/token.h"
#include <string>

PXR_NAMESPACE_USING_DIRECTIVE

int main()
{
    auto stage = UsdStage::CreateInMemory();
    auto record = UsdAecoExampleNativeRecord::Define(stage, SdfPath("/Greeting"));
    std::string greeting;
    if (!record || !record.GetPrim().GetAttribute(
            TfToken("aeco:exampleNative:message")).Get(&greeting)) return 1;
    return greeting == "hello" ? 0 : 2;
}
