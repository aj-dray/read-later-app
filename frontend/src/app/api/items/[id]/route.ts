import { NextResponse } from "next/server";
import { deleteItem } from "@/app/_lib/items";

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  let itemId: string | undefined;
  try {
    const { id } = await params;
    itemId = id;

    if (!itemId) {
      return NextResponse.json(
        { error: "Item ID is required" },
        { status: 400 },
      );
    }

    await deleteItem(itemId);

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Failed to delete item", { itemId, error });

    // Check if it's a 404 error (item not found)
    if (
      error instanceof Error &&
      "code" in error &&
      (error as { code: number }).code === 404
    ) {
      return NextResponse.json({ error: "Item not found" }, { status: 404 });
    }

    return NextResponse.json(
      { error: "Failed to delete item" },
      { status: 500 },
    );
  }
}
