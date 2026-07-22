from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import user_passes_test
from ..forms.admin_forms import UsuarioCreateForm, UsuarioEditForm, RolForm


solo_superadmin = user_passes_test(lambda u: u.is_superuser, login_url="/accounts/login/")


@login_required
@solo_superadmin
def admin_panel(request):
    User = get_user_model()
    total_usuarios = User.objects.count()
    total_activos = User.objects.filter(is_active=True).count()
    total_roles = Group.objects.count()
    return render(request, "inventario/admin/panel.html", {
        "total_usuarios": total_usuarios,
        "total_activos": total_activos,
        "total_roles": total_roles,
    })


@login_required
@solo_superadmin
def admin_usuarios(request):
    User = get_user_model()
    usuarios = User.objects.prefetch_related("groups").order_by("-is_superuser", "-is_staff", "username")
    return render(request, "inventario/admin/usuarios.html", {"usuarios": usuarios})


@login_required
@solo_superadmin
def admin_usuario_create(request):
    form = UsuarioCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Usuario creado correctamente.")
        return redirect("admin_usuarios")
    return render(request, "inventario/admin/usuario_form.html", {"form": form, "titulo": "Nuevo usuario"})


@login_required
@solo_superadmin
def admin_usuario_edit(request, pk):
    User = get_user_model()
    usuario = get_object_or_404(User, pk=pk)
    form = UsuarioEditForm(request.POST or None, instance=usuario)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Usuario '{usuario.username}' actualizado.")
        return redirect("admin_usuarios")
    return render(request, "inventario/admin/usuario_form.html", {
        "form": form,
        "titulo": f"Editar usuario — {usuario.username}",
        "usuario": usuario,
    })


@login_required
@solo_superadmin
@require_POST
def admin_usuario_toggle(request, pk):
    User = get_user_model()
    usuario = get_object_or_404(User, pk=pk)
    if usuario == request.user:
        messages.error(request, "No podés desactivar tu propia cuenta.")
        return redirect("admin_usuarios")
    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=["is_active"])
    estado = "activado" if usuario.is_active else "desactivado"
    messages.success(request, f"Usuario '{usuario.username}' {estado}.")
    return redirect("admin_usuarios")


@login_required
@solo_superadmin
@require_POST
def admin_usuario_delete(request, pk):
    User = get_user_model()
    usuario = get_object_or_404(User, pk=pk)
    if usuario == request.user:
        messages.error(request, "No podés eliminar tu propia cuenta.")
        return redirect("admin_usuarios")
    nombre = usuario.username
    try:
        usuario.delete()
        messages.success(request, f"Usuario '{nombre}' eliminado.")
    except ProtectedError:
        messages.error(
            request,
            f"No se puede eliminar '{nombre}': tiene patrimonios u otros registros asignados. "
            "Reasigná esos registros antes de borrar el usuario.",
        )
    return redirect("admin_usuarios")


@login_required
@solo_superadmin
def admin_roles(request):
    roles = Group.objects.prefetch_related("user_set").order_by("name")
    return render(request, "inventario/admin/roles.html", {"roles": roles})


@login_required
@solo_superadmin
def admin_rol_create(request):
    form = RolForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Rol creado correctamente.")
        return redirect("admin_roles")
    return render(request, "inventario/admin/rol_form.html", {"form": form, "titulo": "Nuevo rol"})


@login_required
@solo_superadmin
def admin_rol_edit(request, pk):
    rol = get_object_or_404(Group, pk=pk)
    form = RolForm(request.POST or None, instance=rol)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Rol '{rol.name}' actualizado.")
        return redirect("admin_roles")
    return render(request, "inventario/admin/rol_form.html", {
        "form": form,
        "titulo": f"Editar rol — {rol.name}",
        "rol": rol,
    })


@login_required
@solo_superadmin
@require_POST
def admin_rol_delete(request, pk):
    rol = get_object_or_404(Group, pk=pk)
    nombre = rol.name
    rol.delete()
    messages.success(request, f"Rol '{nombre}' eliminado.")
    return redirect("admin_roles")
