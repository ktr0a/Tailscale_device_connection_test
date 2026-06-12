from pythonforandroid.recipe import RustCompiledComponentsRecipe


class PydanticcoreRecipe(RustCompiledComponentsRecipe):
    version = "2.41.4"
    url = "https://github.com/pydantic/pydantic-core/archive/refs/tags/v{version}.tar.gz"
    site_packages_name = "pydantic_core"

    def get_recipe_env(self, arch, **kwargs):
        env = super().get_recipe_env(arch, **kwargs)
        # Newer maturin (>= main branch circa 2025) reads ANDROID_API_LEVEL to
        # construct the android_{api}_{arch} wheel platform tag.  p4a builds
        # from a clean env (archs.py get_env starts with env = {}), so the
        # shell-level export never reaches maturin.  Inject it explicitly from
        # ctx.ndk_api (e.g. 24) which is already set by --ndk-api.
        env["ANDROID_API_LEVEL"] = str(self.ctx.ndk_api)
        return env


recipe = PydanticcoreRecipe()
