ROM_LOAD 0x08000000 {
	ROM_START 0x08000000
	{
		log1.o (RomHeader)
	}
	ROM_CRT0 0x080000c0
	{
		log1.o (Init)
	}
	ROM_REMAINDER 0x08000138
	{
		log1.o (Remainder)
	}
}
