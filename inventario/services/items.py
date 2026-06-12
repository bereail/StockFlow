from inventario.models import Item, Toner, Articulo, ActivoPC, Impresora


def item_de_toner(toner: Toner) -> Item:
    item, _ = Item.objects.get_or_create(tipo="TONER", toner=toner)
    return item


def item_de_articulo(articulo: Articulo) -> Item:
    item, _ = Item.objects.get_or_create(tipo="ARTICULO", articulo=articulo)
    return item


def item_de_pc(pc: ActivoPC) -> Item:
    item, _ = Item.objects.get_or_create(tipo="ACTIVO_PC", activo_pc=pc)
    return item


def item_de_impresora(impresora: Impresora) -> Item:
    item, _ = Item.objects.get_or_create(tipo="IMPRESORA", impresora=impresora)
    return item
