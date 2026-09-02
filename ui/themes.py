"""colour palettes only: appearance never changes personality, memory or voice"""
PALETTES = {
    'classic': dict(body='#153e37', panel='#edf2df', face='#b7dfad', ink='#123c34',
                    muted='#5b7361', accent='#f2c65c', button='#d7e5c9', hover='#c4dcb7',
                    entry='#f9faef', compose='#d8e4cb', selection='#c0d8ad', code='#e0e8d3',
                    status='#afc6a9', notice='#805127', blush='#ec9399'),
    'pink': dict(body='#593348', panel='#fbeaf0', face='#f0bfd3', ink='#512f43',
                 muted='#78546a', accent='#f5ce82', button='#ebcedc', hover='#e4b6cd',
                 entry='#fff7fa', compose='#edcfdd', selection='#e6afc9', code='#f0d8e3',
                 status='#e7bed2', notice='#8b445c', blush='#d86a97'),
}


def palette(name):
    return PALETTES.get(name, PALETTES['classic'])
