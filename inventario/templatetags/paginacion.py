from django import template

register = template.Library()


@register.simple_tag
def elided_page_range(page_obj):
    """Rango de páginas con elipsis (…) para no listar cientos de números."""
    return page_obj.paginator.get_elided_page_range(
        page_obj.number, on_each_side=1, on_ends=1
    )
