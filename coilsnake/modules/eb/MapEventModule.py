import yaml
from re import sub

from coilsnake.modules.eb.EbTablesModule import EbTable
from coilsnake.Progress import updateProgress
from coilsnake.modules.eb import EbModule


class MapEventModule(EbModule.EbModule):
    NAME = "Map Events"
    FREE_RANGES = [(0x101598, 0x10187f)]

    _PTR_LOC = 0x70d
    _PTR_BANK_LOC = 0x704

    def __init__(self):
        EbModule.EbModule.__init__(self)
        self._ptrTbl = EbTable(0xD01598)
        self._entries = []

    def read_from_rom(self, rom):
        """
        @type rom: coilsnake.data_blocks.Rom
        """
        self._ptrTbl.readFromRom(rom,
                                 EbModule.toRegAddr(rom.read_multi(self._PTR_LOC, 3)))
        updateProgress(5)
        bank = (rom[self._PTR_BANK_LOC] - 0xc0) << 16
        pct = 45.0 / 20
        for i in range(20):
            addr = bank | self._ptrTbl[i, 0].val()
            tsetEntry = []
            while rom.read_multi(addr, 2) != 0:
                flag = rom.read_multi(addr, 2)
                num = rom.read_multi(addr + 2, 2)
                addr += 4
                changes = []
                for j in range(num):
                    changes.append((rom.read_multi(addr, 2),
                                    rom.read_multi(addr + 2, 2)))
                    addr += 4
                tsetEntry.append((flag, changes))
            self._entries.append(tsetEntry)
            updateProgress(pct)

    def write_to_project(self, resourceOpener):
        out = dict()
        i = 0
        for entry in self._entries:
            entryOut = []
            for (flag, changes) in entry:
                changeOut = {"Event Flag": flag, "Changes": changes}
                entryOut.append(changeOut)
            if not entryOut:
                out[i] = None
            else:
                out[i] = entryOut
            i += 1
        updateProgress(25)
        with resourceOpener("map_changes", "yml") as f:
            s = yaml.dump(out, Dumper=yaml.CSafeDumper)
            s = sub("Event Flag: (\d+)",
                    lambda i: "Event Flag: " + hex(int(i.group(0)[12:])), s)
            f.write(s)
        updateProgress(25)

    def read_from_project(self, resourceOpener):
        with resourceOpener("map_changes", "yml") as f:
            input = yaml.load(f, Loader=yaml.CSafeLoader)
            for mtset in input:
                entry = []
                entryIn = input[mtset]
                if entryIn is not None:
                    for csetIn in entryIn:
                        entry.append((csetIn["Event Flag"],
                                      csetIn["Changes"]))
                self._entries.append(entry)
                updateProgress(50.0 / 20)

    def write_to_rom(self, rom):

        """
        @type rom: coilsnake.data_blocks.Rom
        """
        self._ptrTbl.clear(20)
        blockSize = 0
        for entry in self._entries:
            for (flag, set) in entry:
                blockSize += 4 + 4 * len(set)
            blockSize += 2
        if blockSize > 0xffff:
            raise RuntimeError("Too many map changes")
        loc = rom.allocate(size=blockSize)
        rom[self._PTR_BANK_LOC] = (loc >> 16) + 0xc0
        i = 0
        for entry in self._entries:
            self._ptrTbl[i, 0].setVal(loc & 0xffff)
            for (flag, set) in entry:
                rom.write_multi(loc, flag, 2)
                rom.write_multi(loc + 2, len(set), 2)
                loc += 4
                for (before, after) in set:
                    rom.write_multi(loc, before, 2)
                    rom.write_multi(loc + 2, after, 2)
                    loc += 4
            rom[loc] = 0
            rom[loc + 1] = 0
            loc += 2
            i += 1
            updateProgress(45.0 / 20)
        ptrTblLoc = self._ptrTbl.writeToFree(rom)
        rom.write_multi(self._PTR_LOC, EbModule.toSnesAddr(ptrTblLoc), 3)
        updateProgress(5)