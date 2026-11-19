"""Pascal VOC import. Coordinates are kept as supplied (no implicit -1 shift)."""
import xml.etree.ElementTree as ET


def parse_voc(text, width, height):
    if len(text) > 2_000_000 or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('XML слишком большой или содержит запрещённые объявления.')
    root = ET.fromstring(text)
    if root.tag != 'annotation':
        raise ValueError('Ожидается Pascal VOC XML с корнем annotation.')
    if (int(root.findtext('size/width', '0')), int(root.findtext('size/height', '0'))) != (width, height):
        raise ValueError('Размеры в XML не совпадают с фото. Выберите соответствующее изображение.')
    objects = []
    for obj in root.findall('object'):
        objects.append({'label': obj.findtext('name', '').strip(),
                        'bbox': [float(obj.findtext('bndbox/'+key, 'nan'))
                                 for key in ('xmin', 'ymin', 'xmax', 'ymax')]})
    from generator import validate
    return {'objects': validate({'objects': objects}, (width, height))['objects'],
            'filename': root.findtext('filename', '')}
