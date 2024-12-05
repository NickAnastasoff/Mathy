import os
import re
from PIL import Image, ImageOps, ImageDraw, ImageFont
from PyPDF2 import PdfMerger
from bullet import Bullet, Input, YesNo

# Define the A4 page size in pixels (72 DPI)
A4_PAGE_SIZE = (595, 842)  # width, height at 72 DPI

def natural_sort_key(s):
    """Sort strings containing numbers in a human-expected way."""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split('(\d+)', s)]

def resize_and_align_image(image, page_size, margin, label=None):
    """Resize image to fit within the given page size, maintaining aspect ratio,
    and optionally add margins and labels above the image."""
    img_ratio = image.width / image.height
    page_ratio = page_size[0] / page_size[1]

    # Choose a font size appropriate for the image size
    font_size = int(page_size[1] * 0.02)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()

    # Estimate label height
    if label:
        bbox = font.getbbox(label)
        label_height = (bbox[3] - bbox[1]) + 5  # Add some padding
    else:
        label_height = 0

    # Adjust for margins and label space
    usable_width = page_size[0] - 2 * margin
    usable_height = page_size[1] - 2 * margin - label_height

    if img_ratio > page_ratio:
        new_width = usable_width
        new_height = round(usable_width / img_ratio)
    else:
        new_height = usable_height
        new_width = round(usable_height * img_ratio)

    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Create a white canvas with margins
    canvas = Image.new('RGB', page_size, (255, 255, 255))

    # Position the label
    if label:
        draw = ImageDraw.Draw(canvas)
        label_position = (margin, margin)
        draw.text(label_position, label, fill=(0, 0, 0), font=font)
    else:
        label_height = 0

    # Position the resized image on the canvas with margins and label height
    paste_position = (
        (page_size[0] - new_width) // 2,
        margin + label_height
    )

    # Paste the resized image onto the canvas
    canvas.paste(resized_image, paste_position)

    return canvas

def images_to_pdf(
    directory,
    images_per_page=1,
    delete_images=False,
    margin=0,
    label_images=False,
    sort_by_time=False,
):
    # Get all image files in the directory
    images = [
        f
        for f in os.listdir(directory)
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"))
    ]

    if not images:
        print("No images found in the directory.")
        return

    # Sort images based on user preference
    if sort_by_time:
        images.sort(key=lambda x: os.path.getctime(os.path.join(directory, x)))
    else:
        images.sort(key=natural_sort_key)

    # Define per-image page size
    per_image_page_height = A4_PAGE_SIZE[1] // images_per_page
    per_image_page_size = (
        A4_PAGE_SIZE[0],
        per_image_page_height
    )

    # Create a merger object to combine all pages later
    pdf_merger = PdfMerger()

    current_images = []
    page_number = 1
    image_counter = 1

    for i, img_file in enumerate(images):
        img_path = os.path.join(directory, img_file)
        with Image.open(img_path) as img:
            img = img.convert("RGB")  # Convert to RGB for PDF compatibility

            # Generate label if required
            if label_images:
                label = f"Question {image_counter}"
            else:
                label = None

            current_images.append(
                resize_and_align_image(
                    img, per_image_page_size, margin, label=label
                )
            )

        image_counter += 1

        # Check if the current batch is ready to be saved
        if (i + 1) % images_per_page == 0 or i == len(images) - 1:
            # Combine images onto a single PDF page
            page_canvas = Image.new('RGB', A4_PAGE_SIZE, (255, 255, 255))
            y_offset = 0
            for combined_img in current_images:
                page_canvas.paste(combined_img, (0, y_offset))
                y_offset += per_image_page_height

            # Save the combined page as a temporary PDF
            temp_pdf = f"temp_page_{page_number}.pdf"
            page_canvas.save(temp_pdf, "PDF", quality=95)
            pdf_merger.append(temp_pdf)
            current_images.clear()
            page_number += 1

    # Output the final PDF
    output_pdf = os.path.join(directory, "combined_output.pdf")
    with open(output_pdf, "wb") as f_out:
        pdf_merger.write(f_out)

    # Clean up temporary PDFs
    for i in range(1, page_number):
        os.remove(f"temp_page_{i}.pdf")

    print(f"PDF created successfully at: {output_pdf}")

    # Optionally delete original images
    if delete_images:
        for img_file in images:
            os.remove(os.path.join(directory, img_file))
        print("Original images have been deleted.")

if __name__ == "__main__":
    cli_choices = [
        "Convert images in the current directory to PDF",
        "Specify directory and options",
        "Exit",
    ]
    cli = Bullet(prompt="Choose an option:", choices=cli_choices)
    choice = cli.launch()

    if choice == "Convert images in the current directory to PDF":
        images_to_pdf(os.getcwd())
    elif choice == "Specify directory and options":
        directory_prompt = Input("Enter the directory to scan for images: ")
        directory = directory_prompt.launch()
        if not os.path.isdir(directory):
            print("Invalid directory. Exiting.")
        else:
            # Ask for images per page
            page_prompt = Input("How many images per page (default 1): ")
            images_per_page = page_prompt.launch()
            try:
                images_per_page = int(images_per_page)
                if images_per_page < 1:
                    raise ValueError("Number of images per page must be at least 1.")
            except ValueError as e:
                print(f"Invalid input for images per page: {e}. Using default (1).")
                images_per_page = 1

            # Ask if images should be deleted after processing
            delete_prompt = YesNo(
                "Do you want to delete the original images after creating the PDF? (y/n): "
            )
            delete_images = delete_prompt.launch()

            # Ask for margin size
            margin_prompt = Input("Enter margin size in pixels (default 0): ")
            margin = margin_prompt.launch()
            try:
                margin = int(margin)
                if margin < 0:
                    raise ValueError("Margin size cannot be negative.")
            except ValueError as e:
                print(f"Invalid input for margin size: {e}. Using default (0).")
                margin = 0

            # Ask if images should be labeled
            label_prompt = YesNo(
                "Do you want to label each image with a question number? (y/n): "
            )
            label_images = label_prompt.launch()

            # Ask if images should be sorted by creation time
            sort_prompt = YesNo(
                "Do you want to sort images by creation time? (y/n): "
            )
            sort_by_time = sort_prompt.launch()

            images_to_pdf(
                directory,
                images_per_page,
                delete_images,
                margin,
                label_images,
                sort_by_time,
            )
    else:
        print("Goodbye!")
