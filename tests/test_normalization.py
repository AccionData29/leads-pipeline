from pipeline.normalization.normalize import phone_norm, text_norm

def test_phone_norm(): assert phone_norm("+57 310 482 4081")=="573104824081"
def test_text_norm(): assert text_norm(" Bogotá D.C. ")=="bogota d.c."
